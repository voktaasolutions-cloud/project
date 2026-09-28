from dotenv import load_dotenv
from pathlib import Path

ROOT_DIR = Path(__file__).parent
load_dotenv(ROOT_DIR / '.env')

import os
import logging
import asyncio
from datetime import datetime, timezone, timedelta
from typing import List, Optional

import jwt
try:
    import resend
except ImportError:
    resend = None
import httpx
from fastapi import FastAPI, APIRouter, Request, HTTPException, Depends, UploadFile, File, Query
from fastapi.staticfiles import StaticFiles
from starlette.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field, EmailStr

from database.appwrite_client import appwrite_manager
from repositories.user_repository import UserRepository
from repositories.enquiries_repository import EnquiryRepository
from repositories.reviews_repository import ReviewRepository
from repositories.events_repository import EventRepository
from repositories.settings_repository import SettingsRepository
from repositories import now_iso, parse_datetime, format_iso
from services.auth_service import auth_service, hash_password, verify_password, create_access_token
from services.storage_service import storage_service

# ------------------------------------------------------------------ App Setup
app = FastAPI(title="VOKTAA Solutions API")
api_router = APIRouter(prefix="/api")

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("voktaa")


async def send_enquiry_email(enquiry: dict) -> None:
    """Notify the site owner of a new enquiry. Never blocks/fails the request."""
    api_key = os.environ.get("RESEND_API_KEY", "").strip()
    owner = os.environ.get("OWNER_EMAIL", "").strip()
    if not api_key or not owner:
        return
    try:
        resend.api_key = api_key
        rows = "".join(
            f"<tr><td style='padding:6px 12px;color:#6b7280;font-size:13px'>{k.replace('_',' ').title()}</td>"
            f"<td style='padding:6px 12px;color:#111827;font-size:13px'>{enquiry.get(k) or '-'}</td></tr>"
            for k in ["first_name", "last_name", "email", "phone", "program", "city", "message"]
        )
        html = (
            "<div style='font-family:Arial,sans-serif;max-width:560px;margin:auto'>"
            "<div style='background:#071527;padding:24px 20px'>"
            "<span style='color:#D9A23B;font-weight:bold;font-size:20px;letter-spacing:3px'>VOKTAA</span>"
            "<p style='color:#F2C46D;font-size:12px;margin:6px 0 0'>NEW DEMO ENQUIRY</p></div>"
            "<div style='border:1px solid #eee;border-top:3px solid #D9A23B;padding:8px'>"
            f"<table style='width:100%;border-collapse:collapse'>{rows}</table></div>"
            "<p style='color:#9ca3af;font-size:11px;padding:12px 20px'>Sent automatically from voktaasolutions.com</p></div>"
        )
        params = {
            "from": os.environ.get("SENDER_EMAIL", "onboarding@resend.dev"),
            "to": [owner],
            "subject": f"New Enquiry: {enquiry.get('first_name','')} · {enquiry.get('program') or 'General'}",
            "html": html,
        }
        await asyncio.to_thread(resend.Emails.send, params)
    except Exception as e:  # noqa
        logger.error("Enquiry email failed: %s", e)


async def get_current_admin(request: Request) -> dict:
    auth_header = request.headers.get("Authorization", "")
    token = auth_header[7:] if auth_header.startswith("Bearer ") else None
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = await auth_service.get_user_from_token(token)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid token or user not found")
    return user


# ------------------------------------------------------------------ Pydantic Models
class LoginInput(BaseModel):
    email: EmailStr
    password: str


class EnquiryCreate(BaseModel):
    first_name: str
    last_name: str = ""
    email: EmailStr
    phone: str = ""
    program: str = ""
    city: str = ""
    message: str = ""


class TrackEvent(BaseModel):
    type: str                       # "visit" | "click"
    category: str = ""              # "contact" | "cta" | "program" | "nav"
    label: str = ""                 # e.g. "whatsapp", "Little Voices"
    page: str = ""
    session_id: str = ""


class ReviewCreate(BaseModel):
    name: str
    email: EmailStr
    phone: str = ""
    role: str = ""
    organisation: str = ""
    program: str = ""
    rating: int = 5
    review: str


class ReviewStatusUpdate(BaseModel):
    status: str  # "approved" | "rejected" | "pending"


class ChatMessage(BaseModel):
    session_id: str
    message: str


# ------------------------------------------------------------------ Program Syllabus Catalogue
PROGRAM_SYLLABI = {
    "campus-recruitment-training": {
        "title": "Campus Recruitment Training",
        "source_document": "Voktaa_Course_Wise_Subjects_Content.docx",
        "subjects": [
            "Aptitude & Logical Reasoning", "Group Discussion Techniques",
            "Resume & Cover Letter Building", "Personal Interview Preparation",
            "Verbal & Written Communication", "Body Language & First Impressions",
            "Corporate Etiquette", "Email & Business Writing",
            "Mock Placement Drives", "Industry & Current Affairs Awareness",
            "Confidence Building",
        ],
    },
    "soft-skills-development": {
        "title": "Soft Skills Development",
        "source_document": "Voktaa_Course_Wise_Subjects_Content.docx",
        "subjects": [
            "Communication Skills", "Teamwork & Collaboration", "Time Management",
            "Emotional Intelligence", "Problem-Solving & Decision Making",
            "Adaptability & Flexibility", "Interpersonal Skills", "Conflict Resolution",
            "Active Listening", "Self-Motivation", "Networking Skills",
        ],
    },
    "communication-business-skills": {
        "title": "Communication & Business Skills",
        "source_document": "Voktaa_Course_Wise_Subjects_Content.docx",
        "subjects": [
            "Business Communication Foundations", "Professional Email & Report Writing",
            "Effective Workplace Conversation", "Presentation & Deck Delivery",
            "Cross-Cultural Communication", "Client Pitching & Negotiation",
            "Active Listening & Feedback", "Meeting Facilitation & Minutes",
            "Corporate Vocabulary & Etiquette",
        ],
    },
    "personality-development": {
        "title": "Personality Development",
        "source_document": "Voktaa_Course_Wise_Subjects_Content.docx",
        "subjects": [
            "Self-Awareness & Confidence Building", "Body Language & Non-Verbal Communication",
            "Grooming & Professional Etiquette", "Public Speaking", "Emotional Intelligence",
            "Attitude & Mindset Building", "Goal Setting & Self-Discipline",
            "Stress & Anger Management", "Social Etiquette & Networking",
        ],
    },
    "public-speaking-debate": {
        "title": "Public Speaking & Debate",
        "source_document": "Voktaa_Course_Wise_Subjects_Content.docx",
        "subjects": [
            "Stage Presence & Overcoming Fear", "Speech Structuring & Storytelling",
            "Voice Modulation & Articulation", "Debate Formats & Rebuttal Strategies",
            "Body Language & Micro-Gestures", "Impromptu Speaking (Extempore)",
            "Persuasive Argumentation", "Audience Engagement Techniques",
            "Mic & Podium Management",
        ],
    },
    "interview-skills-mock-gds": {
        "title": "Interview Skills & Mock GDs",
        "source_document": "Voktaa_Course_Wise_Subjects_Content.docx",
        "subjects": [
            "Resume & CV Building", "Types of Interviews (HR, Technical, Panel)",
            "Common Interview Questions & Answers", "Body Language in Interviews",
            "Group Discussion Skills", "Mock Interview Practice",
            "Salary Negotiation Techniques", "Post-Interview Follow-Up Etiquette",
        ],
    },
    "career-guidance-programme": {
        "title": "Career Guidance Programme",
        "source_document": "Voktaa_Course_Wise_Subjects_Content.docx",
        "subjects": [
            "Self-Assessment & Aptitude Analysis", "Career Path Mapping",
            "Skill Gap Identification", "Resume & Portfolio Building",
            "Industry & Job Market Awareness", "Goal Setting & Career Planning",
            "Networking & Personal Branding", "Higher Education & Certification Guidance",
        ],
    },
    "leadership-development": {
        "title": "Leadership Development",
        "source_document": "Voktaa_Course_Wise_Subjects_Content.docx",
        "subjects": [
            "Leadership Styles & Self-Assessment", "Decision Making & Problem Solving",
            "Delegation & Empowerment", "Team Building & Motivation",
            "Emotional Intelligence for Leaders", "Strategic & Critical Thinking",
            "Conflict & Change Management", "Coaching & Mentoring",
            "Effective Leadership Communication", "Performance Management",
        ],
    },
    "corporate-training-modules": {
        "title": "Corporate Training Modules",
        "source_document": "Voktaa_Course_Wise_Subjects_Content.docx",
        "subjects": [
            "Workplace Communication", "Professional Email & Report Writing",
            "Corporate Etiquette & Grooming", "Presentation Skills", "Team Collaboration",
            "Time & Priority Management", "Conflict Management at Workplace",
            "Stress Management", "Cross-Functional Coordination",
            "Business Communication Tools",
        ],
    },
    "company-specific-training": {
        "title": "Company Specific Training",
        "source_document": "Voktaa_Course_Wise_Subjects_Content.docx",
        "subjects": [
            "Organizational Culture & Values Orientation", "Role-Specific Communication Standards",
            "Company Process & SOP Training", "Client Handling & Domain Etiquette",
            "Tools & Software Familiarization", "Compliance & Policy Awareness",
            "Team Integration Workshops", "Customized Case Studies & Simulations",
            "Performance Expectation Alignment",
        ],
    },
    "technical-skills": {
        "title": "Technical Skills",
        "source_document": "Voktaa_Course_Wise_Subjects_Content.docx",
        "subjects": [
            "Generative AI Tools & Prompt Engineering", "Python Programming",
            "Data Analysis & Visualization (Excel, Power BI)", "Cloud Computing Fundamentals (AWS / Azure / GCP)",
            "Cybersecurity Fundamentals", "DevOps & CI/CD Automation",
            "Web Development (HTML, CSS, JavaScript Frameworks)", "SQL & Database Management",
            "Machine Learning Fundamentals", "Git & Version Control",
            "MS Office & AI Copilot Tools", "UI/UX Design Basics",
            "Low-Code / No-Code App Development", "Digital Marketing & Social Media Tools",
            "Tally & Accounting Software",
        ],
    },
    "faculty-development-programmes": {
        "title": "Faculty Development Programmes",
        "source_document": "Voktaa_Course_Wise_Subjects_Content.docx",
        "subjects": [
            "Modern Teaching Pedagogies", "Curriculum & Lesson Planning",
            "Classroom Management Techniques", "Student Engagement Strategies",
            "Assessment & Evaluation Methods", "Technology-Integrated Teaching",
            "Communication Skills for Educators", "Research & Publication Skills",
            "Outcome-Based Education (OBE)",
        ],
    },
    "train-the-trainer-programme": {
        "title": "Train-the-Trainer Programme",
        "source_document": "Voktaa_Course_Wise_Subjects_Content.docx",
        "subjects": [
            "Instructional Design Basics", "Facilitation Skills",
            "Presentation Skills for Trainers", "Content Development & Session Planning",
            "Handling Difficult Participants", "Training Delivery Techniques",
            "Use of Training Aids & Technology", "Feedback & Evaluation Methods",
            "Training Needs Analysis",
        ],
    },
}

# Add URL aliases to PROGRAM_SYLLABI
PROGRAM_SYLLABI["tech-skills"] = PROGRAM_SYLLABI["technical-skills"]
PROGRAM_SYLLABI["corporate-training"] = PROGRAM_SYLLABI["corporate-training-modules"]
PROGRAM_SYLLABI["career-guidance"] = PROGRAM_SYLLABI["career-guidance-programme"]
PROGRAM_SYLLABI["interview-skills"] = PROGRAM_SYLLABI["interview-skills-mock-gds"]
PROGRAM_SYLLABI["faculty-development"] = PROGRAM_SYLLABI["faculty-development-programmes"]
PROGRAM_SYLLABI["faculty-development-fdp"] = PROGRAM_SYLLABI["faculty-development-programmes"]
PROGRAM_SYLLABI["train-the-trainer"] = PROGRAM_SYLLABI["train-the-trainer-programme"]
PROGRAM_SYLLABI["public-speaking"] = PROGRAM_SYLLABI["public-speaking-debate"]


# ------------------------------------------------------------------ Health Check Endpoint
@api_router.get("/health")
async def health_check():
    """Verify FastAPI backend and database status."""
    try:
        from database.connection import AsyncSessionLocal, DB_PROVIDER
        from sqlalchemy import text
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "database": "connected",
            "provider": DB_PROVIDER
        }
    except Exception as e:
        return {
            "status": "degraded",
            "database": f"error: {str(e)}",
            "provider": "mysql"
        }



# ------------------------------------------------------------------ Auth Routes
@api_router.post("/auth/login")
async def login(data: LoginInput):
    res = await auth_service.authenticate_user(data.email, data.password)
    if not res:
        try:
            await seed_admin()
            res = await auth_service.authenticate_user(data.email, data.password)
        except Exception as seed_err:
            logger.warning("Lazy seed_admin attempt notice: %s", seed_err)
    if not res:
        raise HTTPException(status_code=401, detail="Invalid email or password")
    return res



@api_router.get("/auth/me")
async def me(admin: dict = Depends(get_current_admin)):
    return admin


# ------------------------------------------------------------------ Public Routes
@api_router.get("/")
async def root():
    return {"message": "VOKTAA Solutions API"}


@api_router.get("/programs/{program_slug}")
async def get_program_syllabus(program_slug: str):
    syllabus = PROGRAM_SYLLABI.get(program_slug)
    if syllabus is None:
        raise HTTPException(status_code=404, detail="Program not found")
    return {
        "slug": program_slug,
        "title": syllabus["title"],
        "available": bool(syllabus["source_document"] and syllabus["subjects"]),
        "source_document": syllabus["source_document"],
        "subjects": syllabus["subjects"],
    }


@api_router.post("/track")
async def track(event: TrackEvent, request: Request):
    doc = event.model_dump()
    doc["ip"] = request.client.host if request.client else ""
    await EventRepository.create(None, doc)
    return {"ok": True}


@api_router.post("/enquiries")
async def create_enquiry(data: EnquiryCreate, request: Request):
    doc = data.model_dump()
    doc["ip"] = request.client.host if request.client else ""
    enquiry = await EnquiryRepository.create(None, doc)
    await EventRepository.create(None, {
        "type": "submission", "category": "enquiry", "label": data.program,
        "page": "/contact", "session_id": "", "ip": doc["ip"],
    })
    await send_enquiry_email(doc)
    return {"ok": True, "id": enquiry.id}


@api_router.post("/chat")
async def chat_with_bot(payload: ChatMessage):
    text = (payload.message or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Empty message.")
    if len(text) > 2000:
        text = text[:2000]
    try:
        reply = "Chat is temporarily disabled."
        await EventRepository.create(None, {
            "type": "click", "category": "chat", "label": text[:120],
            "page": "/chat", "session_id": payload.session_id or "",
        })
        return {"reply": reply}
    except Exception as e:
        logger.error("chat error: %s", e)
        raise HTTPException(status_code=502, detail="chat_unavailable")


# ------------------------------------------------------------------ WhatsApp Webhook Helper & Routes
VOKTAA_SYSTEM_PROMPT = """You are the official AI Assistant for VOKTAA Solutions — a premier Soft Skills, CRT (Campus Recruitment Training), Spoken English, and Professional Etiquette Training Academy located in Guntur, Andhra Pradesh, India.
Founder & CEO: P. RAJA SEKHAR.
Tagline: Speak. Shine. Succeed.
Key Offerings: Campus Recruitment Training (CRT), Soft Skills & Spoken English, Public Speaking & Debate, Leadership Development, Corporate Training, Faculty Development Programmes (FDP), Train-the-Trainer (TTT).
WhatsApp / Call: +91 74161 13199
Email: voktaasolutions@gmail.com
Website: https://voktaa.com
Be professional, polite, encouraging, and helpful. Always invite users to book a free demo session or visit https://voktaa.com/contact."""


def get_voktaa_bot_reply(user_text: str) -> str:
    text = (user_text or "").lower().strip()
    if any(k in text for k in ["demo", "book", "trial", "schedule", "register", "join", "session", "hi", "hello", "hey"]):
        return (
            "Thank you for considering VOKTAA! 🎓\n\n"
            "VOKTAA Solutions helps engineering graduates, college students, educators, and corporate teams communicate with confidence, think critically, and lead effectively.\n\n"
            "We offer:\n\n"
            "• Campus Recruitment Training (CRT)\n"
            "• Soft Skills Development\n"
            "• Corporate Training\n"
            "• Train-the-Trainer\n"
            "• Career Guidance & Leadership Development\n\n"
            "What would you like to know more about?\n\n"
            "1. Book a free demo (https://voktaa.com/contact)\n"
            "2. Explore our courses (https://voktaa.com/programs)\n"
            "3. Talk to our team (+91 74161 13199)"
        )
    elif any(k in text for k in ["crt", "placement", "campus", "recruitment", "aptitude", "interview", "course", "program", "training"]):
        return (
            "VOKTAA Training Programmes 📚\n\n"
            "• Campus Recruitment Training (CRT): Aptitude, GD, Mock Technical & HR Interviews.\n"
            "• Soft Skills Development: Spoken English, Communication & Workplace Etiquette.\n"
            "• Public Speaking & Debate: Stage presence, voice modulation & storytelling.\n"
            "• Leadership Development: Strategic thinking & team management.\n"
            "• Corporate & Faculty Training: Customized modules for institutions.\n\n"
            "Explore all programmes at https://voktaa.com/programs or reply to speak with our team!"
        )
    elif any(k in text for k in ["contact", "talk", "team", "phone", "number", "call", "whatsapp", "email"]):
        return (
            "Contact VOKTAA Solutions 📞\n\n"
            "Gowripatnam Kavya (Co-ordinator)\n"
            "Phone / WhatsApp: +91 74161 13199\n"
            "Email: voktaasolutions@gmail.com\n"
            "Website: https://voktaa.com\n"
            "Location: Guntur, Andhra Pradesh, India"
        )
    else:
        return (
            "Thank you for contacting VOKTAA Solutions! 🌟 Speak. Shine. Succeed.\n\n"
            "We provide industry-focused soft skills, spoken English, and campus placement training across Andhra Pradesh.\n\n"
            "How can we assist you today? Feel free to ask about our training programmes or book a free demo session at https://voktaa.com/contact!"
        )


@api_router.get("/webhook/whatsapp")
async def verify_whatsapp_webhook(
    mode: Optional[str] = Query(None, alias="hub.mode"),
    token: Optional[str] = Query(None, alias="hub.verify_token"),
    challenge: Optional[str] = Query(None, alias="hub.challenge")
):
    """Handles the one-time verification handshake from Meta."""
    verify_token = os.environ.get("WHATSAPP_VERIFY_TOKEN", "voktaa_whatsapp_verify_123")
    if mode == "subscribe" and token == verify_token:
        logger.info("WhatsApp Webhook verified successfully!")
        try:
            return int(challenge)
        except (ValueError, TypeError):
            return challenge
    raise HTTPException(status_code=403, detail="Forbidden")


@api_router.post("/webhook/whatsapp")
async def handle_whatsapp_message(request: Request):
    """Handles incoming messages from WhatsApp users."""
    logger.info("[STAGE 1] Incoming WhatsApp webhook hit.")
    try:
        data = await request.json()
    except Exception as e:
        logger.error("[STAGE 1 FAIL] Malformed JSON payload: %s", e)
        return {"status": "INVALID_JSON"}

    try:
        entry = data.get("entry", [{}])[0]
        changes = entry.get("changes", [{}])[0]
        value = changes.get("value", {})

        # Ignore status updates (delivery, read receipts)
        if "messages" not in value:
            statuses = value.get("statuses", [])
            if statuses:
                logger.info("[STAGE 1 NOTE] Received status update (delivery/read): %s", statuses[0].get("status"))
            return {"status": "EVENT_RECEIVED"}

        message_data = value["messages"][0]
        if message_data.get("type") != "text":
            logger.info("[STAGE 1 NOTE] Ignoring non-text message type: %s", message_data.get("type"))
            return {"status": "EVENT_RECEIVED"}

        sender_phone = message_data.get("from", "")
        incoming_text = message_data.get("text", {}).get("body", "")
        meta_target_phone_id = value.get("metadata", {}).get("phone_number_id", "")

        logger.info("[STAGE 2] Message parsed. From: %s | Meta Target Phone ID: %s | Text: '%s'", sender_phone, meta_target_phone_id, incoming_text)

        # 1. Generate bot response using AI / Knowledge Base logic
        bot_reply = None
        try:
            llm_key = os.environ.get("EMERGENT_LLM_KEY", "").strip()
            if llm_key:
                try:
                    from emergentintegrations.llm import LlmChat, UserMessage
                    chat = LlmChat(
                        api_key=llm_key,
                        session_id=f"wa-{sender_phone}",
                        system_message=VOKTAA_SYSTEM_PROMPT,
                    ).with_model("anthropic", "claude-sonnet-4-5")
                    bot_reply = await chat.send_message(UserMessage(text=incoming_text))
                except Exception as ai_err:
                    logger.warning("[STAGE 3 NOTE] Emergent LLM chat notice: %s. Using VOKTAA bot response fallback.", ai_err)
                    bot_reply = get_voktaa_bot_reply(incoming_text)
            else:
                bot_reply = get_voktaa_bot_reply(incoming_text)
            logger.info("[STAGE 3] Reply generated successfully.")
        except Exception as bot_err:
            logger.error("[STAGE 3 FAIL] Chatbot generation error: %s", bot_err)
            bot_reply = get_voktaa_bot_reply(incoming_text)

        # 2. Outbound Dispatch to Meta Graph API
        phone_id = os.environ.get("WHATSAPP_PHONE_ID", "").strip()
        wa_token = os.environ.get("WHATSAPP_ACCESS_TOKEN", "").strip()

        logger.info("[STAGE 4] Credentials check: WHATSAPP_PHONE_ID=%s | WHATSAPP_ACCESS_TOKEN=%s", "SET" if phone_id else "MISSING", "SET" if wa_token else "MISSING")

        if not phone_id or not wa_token:
            logger.error("[STAGE 4 FAIL] Missing environment variables on server (WHATSAPP_PHONE_ID or WHATSAPP_ACCESS_TOKEN). Bypassing outbound call.")
            return {"status": "EVENT_RECEIVED"}

        url = f"https://graph.facebook.com/v21.0/{phone_id}/messages"
        headers = {
            "Authorization": f"Bearer {wa_token}",
            "Content-Type": "application/json"
        }
        payload = {
            "messaging_product": "whatsapp",
            "recipient_type": "individual",
            "to": sender_phone,
            "type": "text",
            "text": {
                "preview_url": False,
                "body": str(bot_reply)
            }
        }

        logger.info("[STAGE 5] Sending POST to Graph API: %s -> Recipient: %s", url, sender_phone)
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            logger.info("[STAGE 6] Meta Response HTTP %s: %s", resp.status_code, resp.text)
            resp.raise_for_status()
            logger.info("[SUCCESS] Successfully replied to WhatsApp user: %s", sender_phone)

        return {"status": "EVENT_RECEIVED"}

    except httpx.HTTPStatusError as http_err:
        logger.error("[STAGE 6 FAIL] Graph API Error: %s - %s", http_err.response.status_code, http_err.response.text)
        return {"status": "EVENT_RECEIVED"}
    except Exception as e:
        logger.error("[FATAL HANDLER ERROR]: %s", e, exc_info=True)
        return {"status": "EVENT_RECEIVED"}


# ------------------------------------------------------------------ Admin Routes
@api_router.get("/admin/enquiries")
async def list_enquiries(admin: dict = Depends(get_current_admin)):
    return await EnquiryRepository.list_all(None)


# ---------------- Reviews ----------------
@api_router.post("/reviews")
async def submit_review(data: ReviewCreate, request: Request):
    if not data.review or len(data.review.strip()) < 5:
        raise HTTPException(status_code=400, detail="Review is too short.")
    doc = data.model_dump()
    doc["ip"] = request.client.host if request.client else ""
    created = await ReviewRepository.create(None, doc)
    await EventRepository.create(None, {
        "type": "submission", "category": "review", "label": data.program or data.role,
        "page": "/reviews", "session_id": "", "ip": doc["ip"],
    })
    review_id = created.get("id") if isinstance(created, dict) else ""
    return {"ok": True, "id": review_id, "message": "Thanks! Your review is now live on the site."}


@api_router.get("/reviews")
async def public_reviews(limit: int = 100):
    limit = max(1, min(200, limit))
    return await ReviewRepository.list_public(None, limit)


@api_router.get("/admin/reviews")
async def admin_reviews(admin: dict = Depends(get_current_admin)):
    return await ReviewRepository.list_all(None)


@api_router.patch("/admin/reviews/{review_id}")
async def update_review_status(review_id: str, body: ReviewStatusUpdate, admin: dict = Depends(get_current_admin)):
    if body.status not in {"approved", "rejected", "pending"}:
        raise HTTPException(status_code=400, detail="Invalid status")
    success = await ReviewRepository.update_status(None, review_id, body.status)
    if not success:
        raise HTTPException(status_code=404, detail="Review not found")
    return {"ok": True}


@api_router.delete("/admin/reviews/{review_id}")
async def delete_review(review_id: str, admin: dict = Depends(get_current_admin)):
    success = await ReviewRepository.delete(None, review_id)
    if not success:
        raise HTTPException(status_code=404, detail="Review not found")
    return {"ok": True}


# ---------------- Admin Upload Endpoint ----------------
@api_router.post("/admin/upload")
async def upload_media(file: UploadFile = File(...), folder: str = "images", admin: dict = Depends(get_current_admin)):
    try:
        content = await file.read()
        key, url = await storage_service.upload_file(content, file.filename or "upload.bin", file.content_type or "", folder=folder)
        return {"ok": True, "key": key, "url": url}
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error("Upload error: %s", e)
        raise HTTPException(status_code=500, detail="Upload failed.")


# ---------------- Settings ----------------
@api_router.get("/settings")
async def public_settings():
    return await SettingsRepository.get_settings(None)


@api_router.patch("/admin/settings")
async def update_settings(body: dict, admin: dict = Depends(get_current_admin)):
    return await SettingsRepository.update_settings(None, body)


@api_router.get("/admin/analytics")
async def analytics(admin: dict = Depends(get_current_admin)):
    total_visits = await EventRepository.count_by_type(None, "visit")
    submissions = await EnquiryRepository.count_all(None)
    contact_clicks = await EventRepository.count_by_type_category(None, "click", "contact")
    total_clicks = await EventRepository.count_by_type(None, "click")
    unique_visitors = await EventRepository.distinct_session_visitors(None)

    program_breakdown = await EnquiryRepository.program_breakdown(None)
    program_clicks = await EventRepository.click_label_breakdown(None)
    visits_over_time = await EventRepository.daily_visits_last_14_days(None)
    page_views = await EventRepository.page_view_breakdown(None)
    recent_enquiries = await EnquiryRepository.list_all(None, limit=10)

    return {
        "totals": {
            "visits": total_visits,
            "unique_visitors": unique_visitors,
            "submissions": submissions,
            "contact_clicks": contact_clicks,
            "total_clicks": total_clicks,
        },
        "program_breakdown": program_breakdown,
        "program_clicks": program_clicks,
        "visits_over_time": visits_over_time,
        "page_views": page_views,
        "recent_enquiries": recent_enquiries,
    }


# ------------------------------------------------------------------ Startup & Seed
async def seed_admin():
    from database.connection import init_db
    try:
        await init_db()
    except Exception as e:
        logger.warning("init_db notice inside seed_admin: %s", e)

    admin_emails = [
        os.environ.get("ADMIN_EMAIL", "admin@voktaa.com").lower().strip(),
        "voktaasolutions@gmail.com"
    ]

    admin_password = os.environ.get("ADMIN_PASSWORD", "admin123")
    
    for email in admin_emails:
        if not email:
            continue
        existing = await UserRepository.get_by_email(None, email)
        if existing is None:
            await UserRepository.create(
                None,
                email=email,
                password_hash=hash_password(admin_password),
                name="P. Raja Sekhar",
                role="admin",
            )
            logger.info("Admin seeded: %s", email)
        elif not verify_password(admin_password, existing.password_hash):
            await UserRepository.update_password(None, email, hash_password(admin_password))
            logger.info("Admin password updated: %s", email)

    # Seed initial baseline reviews if missing
    try:
        existing_reviews = await ReviewRepository.list_public(None, limit=200)
        existing_names = {r.name.lower().strip() for r in existing_reviews if getattr(r, 'name', None)}
        initial_data = [
            {
                "name": "Tejasri Penubothu",
                "role": "Student",
                "organisation": "Student",
                "program": "Soft Skills Development",
                "rating": 5,
                "review": "I started using VOKTAA Solutions last week to improve my communication skills, leadership qualities, and interview skills. The training sessions are engaging, well-organized, and easy to understand. The trainers explain every concept clearly with practical examples, which has helped me build confidence. Whenever I had a question, the support team responded quickly and was very helpful. Overall, it has been a great learning experience, and I highly recommend VOKTAA Solutions to anyone looking to improve their soft skills.",
                "status": "approved"
            },
            {
                "name": "Sahithi Srinivas S",
                "role": "Student",
                "organisation": "Student",
                "program": "Campus Recruitment Training",
                "rating": 5,
                "review": "I started using VOKTAA Solutions last week to fix my communication skills, leadership qualities and Interview Tips. The app is very clean and fast. When I had a question, their online/offline sessions helped my interviews and the support team replied in minutes. Highly recommend.",
                "status": "approved"
            },
            {
                "name": "N Venkata Bhargavi",
                "role": "Student",
                "organisation": "Student",
                "program": "Communication Skills",
                "rating": 5,
                "review": "This session will definitely be useful for those who want to build a strong foundation on communication skills and also boost them with confidence to face the interviews. I learned a lot of tips which helped me in my interviews.",
                "status": "approved"
            },
            {
                "name": "Anumula Abhinaya",
                "role": "Student",
                "organisation": "Student",
                "program": "Public Speaking & Debate",
                "rating": 5,
                "review": "The session was very useful and interactive. I learned many things that will help me improve my communication and confidence.",
                "status": "approved"
            },
            {
                "name": "VOKTAA Student",
                "role": "Student",
                "organisation": "Student",
                "program": "Soft Skills & Communication",
                "rating": 5,
                "review": "I joined the program to improve my communication skills, but I gained much more than that. It helped me become more confident, improve my body language, and interact professionally with others.",
                "status": "approved"
            }
        ]
        for rev in initial_data:
            if rev["name"].lower().strip() not in existing_names:
                await ReviewRepository.create(None, rev)
                logger.info("Seeded missing baseline review: %s", rev["name"])
    except Exception as rev_err:
        logger.warning("Seed initial reviews notice: %s", rev_err)



@app.on_event("startup")
async def on_startup():
    from database.connection import init_db
    try:
        await init_db()
        await seed_admin()
    except Exception as e:
        logger.warning("Startup DB initialization notice: %s", e)



app.include_router(api_router)

# Mount local uploads directory for static file serving
uploads_dir = Path(os.environ.get("UPLOAD_DIR", "uploads"))
uploads_dir.mkdir(parents=True, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=str(uploads_dir)), name="uploads")

cors_origins_raw = os.environ.get('CORS_ORIGINS', 'https://voktaa.com,https://www.voktaa.com,https://voktaasolutions.com,https://www.voktaasolutions.com,http://localhost:3000')
origins_list = [o.strip() for o in cors_origins_raw.split(',') if o.strip()]

app.add_middleware(
    CORSMiddleware,
    allow_credentials=True,
    allow_origins=origins_list if origins_list else ["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


if __name__ == "__main__":
    import uvicorn
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run("server:app", host="0.0.0.0", port=port, reload=False)


