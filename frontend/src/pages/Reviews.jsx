import React, { useEffect, useState } from "react";
import { Star, ArrowRight, CheckCircle2, MessageSquare, Brain, TrendingUp } from "lucide-react";
import { motion } from "framer-motion";
import { toast } from "sonner";
import {
  Select, SelectContent, SelectItem, SelectTrigger, SelectValue,
} from "../components/ui/select";
import { Reveal, StaggerGroup, StaggerItem } from "../components/Reveal";
import { SectionLabel, PageHero, StagePedestalDisc } from "../components/shared";
import { getPublicReviews, submitReview, INITIAL_FALLBACK_REVIEWS } from "../lib/api";
import SEO from "../components/SEO";
import Breadcrumbs from "../components/Breadcrumbs";
import { PAGE_SEO, ORGANIZATION_SCHEMA, PRIMARY_ORG_ID } from "../data/seoData";

const ROLE_OPTIONS = ["Student", "Placement Officer", "Corporate Professional", "Educator", "Other"];
const PROGRAM_OPTIONS = [
  "Campus Recruitment Training", "Soft Skills Development", "Communication Skills",
  "Personality Development", "Public Speaking & Debate", "Interview Skills",
  "Leadership Development", "Corporate Training", "Train-the-Trainer", "Other",
];

const Stars = ({ value = 5, onChange, size = 20, testid }) => {
  const [hover, setHover] = useState(0);
  return (
    <div className="flex items-center gap-1" data-testid={testid}>
      {[1, 2, 3, 4, 5].map((v) => (
        <button
          key={v}
          type={onChange ? "button" : undefined}
          onClick={() => onChange && onChange(v)}
          onMouseEnter={() => onChange && setHover(v)}
          onMouseLeave={() => onChange && setHover(0)}
          className={onChange ? "cursor-pointer transition-transform hover:scale-110" : "cursor-default"}
          aria-label={`${v} star${v > 1 ? "s" : ""}`}
        >
          <Star size={size} className={(hover || value) >= v ? "text-amber-400 fill-amber-400 drop-shadow-sm" : "text-purple-200/80"} />
        </button>
      ))}
    </div>
  );
};

const ReviewCard = ({ r }) => (
  <div className="card-purple bg-white/90 backdrop-blur-2xl border-2 border-white/95 p-7 md:p-8 h-full rounded-3xl shadow-[0_20px_45px_rgba(108,92,231,0.12)] hover:shadow-[0_30px_60px_rgba(108,92,231,0.22)] hover:-translate-y-2 transition-all duration-300 flex flex-col justify-between group" data-testid={`review-card-${r.id}`}>
    <div>
      <div className="flex items-center justify-between gap-2 mb-4">
        <Stars value={r.rating} size={18} />
        <span className="font-mono text-[10px] uppercase tracking-wider text-purple-900 bg-purple-100/90 font-bold px-3 py-1 rounded-full shadow-inner">
          {r.role || "Student"}
        </span>
      </div>
      <p className="font-medium text-purple-950 text-base sm:text-lg leading-relaxed text-left mt-2">
        "{r.review}"
      </p>
    </div>

    <div className="mt-6 pt-5 border-t border-purple-100/80 flex items-center justify-between gap-3 flex-wrap">
      <div>
        <p className="font-heading font-extrabold text-purple-950 text-base">{r.name}</p>
        <p className="text-purple-900/70 text-xs font-semibold mt-0.5">{r.organisation || r.program || "VOKTAA Learner"}</p>
      </div>
      <div className="w-8 h-8 rounded-full bg-purple-100/80 text-purple-600 flex items-center justify-center font-heading font-bold text-xs shadow-inner">
        {r.name ? r.name.charAt(0).toUpperCase() : "V"}
      </div>
    </div>
  </div>
);

const Reviews = () => {
  useEffect(() => { document.title = "Student & Partner Reviews | VOKTAA Solutions"; }, []);

  const [reviews, setReviews] = useState(INITIAL_FALLBACK_REVIEWS);
  const [activeTab, setActiveTab] = useState("all");
  const [visible, setVisible] = useState(6);
  const [loadingList, setLoadingList] = useState(false);

  const empty = { name: "", email: "", phone: "", role: "", organisation: "", program: "", rating: 5, review: "" };
  const [form, setForm] = useState(empty);
  const [submitted, setSubmitted] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const set = (k) => (e) => setForm((f) => ({ ...f, [k]: e.target.value }));

  const verifiedCount = reviews.length;
  const verifiedAvg = verifiedCount > 0
    ? (reviews.reduce((acc, r) => acc + (Number(r.rating) || 5), 0) / verifiedCount).toFixed(1)
    : "5.0";

  const aggregateSchema = verifiedCount > 0 ? {
    "@context": "https://schema.org",
    "@type": "EducationalOrganization",
    "@id": PRIMARY_ORG_ID,
    "name": "VOKTAA Solutions",
    "aggregateRating": {
      "@type": "AggregateRating",
      "ratingValue": verifiedAvg,
      "reviewCount": String(verifiedCount),
      "bestRating": "5",
      "worstRating": "1"
    }
  } : null;

  const load = async () => {
    try {
      const data = await getPublicReviews();
      if (Array.isArray(data) && data.length > 0) {
        setReviews(data);
      }
    } catch {
      /* silent catch handled by getPublicReviews fallback */
    }
  };

  useEffect(() => { load(); }, []);

  const submit = async (e) => {
    e.preventDefault();
    if (!form.name.trim() || !form.email.trim() || !form.role || !form.program || !form.review.trim() || !form.rating) {
      toast.error("Please fill all required fields and select a rating.");
      return;
    }
    setSubmitting(true);
    try {
      await submitReview(form);
      setSubmitted(true);
      toast.success("Review posted successfully!");
      setForm(empty);
      load();
    } catch (err) {
      toast.error(err.message || "Something went wrong. Try again.");
    } finally {
      setSubmitting(false);
    }
  };

  // Filter logic
  const filteredReviews = reviews.filter((r) => {
    if (activeTab === "student") return (r.role || "").toLowerCase().includes("student");
    if (activeTab === "officer") return (r.role || "").toLowerCase().includes("officer") || (r.role || "").toLowerCase().includes("placement");
    if (activeTab === "corporate") return (r.role || "").toLowerCase().includes("corporate") || (r.role || "").toLowerCase().includes("educator") || (r.role || "").toLowerCase().includes("manager");
    return true;
  });

  const shown = filteredReviews.slice(0, visible);

  return (
    <>
      <PageHero
        testid="reviews-hero"
        label="Reviews"
        title="In their own"
        gold="words."
        subtitle="Real reactions from students, placement officers, and corporate partners, collected directly from our active training cohorts."
      >
        <div className="relative flex flex-col items-center justify-center w-full">
          <StagePedestalDisc />
          <div className="relative w-full max-w-lg flex items-center justify-center gap-1.5 sm:gap-4 z-10 py-2 px-1 sm:px-0">
            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.3, duration: 0.6 }}
              whileHover={{ y: -8 }}
              className="card-purple bg-white/95 backdrop-blur-2xl border-2 border-white/95 p-2.5 sm:p-6 rounded-2xl sm:rounded-3xl shadow-[0_20px_45px_rgba(108,92,231,0.15)] flex flex-col items-center text-center flex-1 max-w-[110px] sm:max-w-none sm:w-44 group"
            >
              <div className="w-8 h-8 sm:w-12 sm:h-12 rounded-xl sm:rounded-2xl bg-purple-100/90 text-purple-600 flex items-center justify-center shadow-inner group-hover:bg-purple-600 group-hover:text-white transition-colors duration-300">
                <MessageSquare size={18} className="sm:w-[22px] sm:h-[22px]" />
              </div>
              <span className="font-heading font-extrabold text-[10px] sm:text-sm text-purple-950 mt-2 sm:mt-4 tracking-tight">COMMUNICATE</span>
              <span className="text-purple-900/70 text-[9px] sm:text-xs mt-0.5 sm:mt-1 font-semibold">with Confidence</span>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 30 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.45, duration: 0.6 }}
              whileHover={{ y: -8 }}
              className="card-purple bg-white backdrop-blur-2xl border-2 border-white p-3.5 sm:p-7 rounded-2xl sm:rounded-3xl shadow-[0_25px_55px_rgba(108,92,231,0.22)] flex flex-col items-center text-center flex-1 max-w-[125px] sm:max-w-none sm:w-48 -mt-4 sm:-mt-8 group z-20"
            >
              <div className="w-10 h-10 sm:w-14 sm:h-14 rounded-xl sm:rounded-2xl bg-purple-600 text-white flex items-center justify-center shadow-md shadow-purple-500/30 group-hover:scale-110 transition-transform duration-300">
                <Brain size={22} className="sm:w-[26px] sm:h-[26px]" />
              </div>
              <span className="font-heading font-extrabold text-xs sm:text-base text-purple-950 mt-2 sm:mt-4 tracking-tight">THINK</span>
              <span className="text-purple-900/70 text-[10px] sm:text-sm mt-0.5 sm:mt-1 font-semibold">Critically</span>
            </motion.div>

            <motion.div
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: 0.6, duration: 0.6 }}
              whileHover={{ y: -8 }}
              className="card-purple bg-white/95 backdrop-blur-2xl border-2 border-white/95 p-2.5 sm:p-6 rounded-2xl sm:rounded-3xl shadow-[0_20px_45px_rgba(108,92,231,0.15)] flex flex-col items-center text-center flex-1 max-w-[110px] sm:max-w-none sm:w-44 group"
            >
              <div className="w-8 h-8 sm:w-12 sm:h-12 rounded-xl sm:rounded-2xl bg-purple-100/90 text-purple-600 flex items-center justify-center shadow-inner group-hover:bg-purple-600 group-hover:text-white transition-colors duration-300">
                <TrendingUp size={18} className="sm:w-[22px] sm:h-[22px]" />
              </div>
              <span className="font-heading font-extrabold text-[10px] sm:text-sm text-purple-950 mt-2 sm:mt-4 tracking-tight">LEAD</span>
              <span className="text-purple-900/70 text-[9px] sm:text-xs mt-0.5 sm:mt-1 font-semibold">Effectively</span>
            </motion.div>
          </div>
        </div>
      </PageHero>

      {/* REVIEWS DISPLAY */}
      <section className="relative bg-gradient-to-br from-purple-100/70 via-indigo-50/40 to-cyan-50/50 pt-2 md:pt-4 pb-12 overflow-hidden" data-testid="reviews-display">
        <div className="absolute top-10 left-10 w-96 h-96 bg-purple-300/30 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute bottom-10 right-10 w-96 h-96 bg-cyan-300/30 rounded-full blur-3xl pointer-events-none" />
        <div className="absolute inset-0 dot-grid dot-grid-fade opacity-30 pointer-events-none" />

        <div className="relative max-w-7xl mx-auto px-6 md:px-12 z-10">
          <div className="flex flex-wrap items-center justify-center gap-3 mb-12">
            {[
              { id: "all", label: "All Reviews" },
              { id: "student", label: "Students" },
              { id: "officer", label: "Placement Officers" },
              { id: "corporate", label: "Corporate & Faculty" }
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => { setActiveTab(tab.id); setVisible(6); }}
                className={`px-5 py-2.5 rounded-full text-xs font-mono font-bold uppercase tracking-wider transition-all duration-300 shadow-sm ${
                  activeTab === tab.id
                    ? "bg-gradient-to-r from-purple-600 to-indigo-600 text-white shadow-purple-500/25 scale-105"
                    : "bg-white/80 backdrop-blur-md border border-purple-100 text-purple-950 hover:bg-white"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>

          {loadingList ? (
            <p className="text-purple-950 font-bold text-center font-mono text-sm">Loading verified database reviews…</p>
          ) : (
            <>
              <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6 sm:gap-8">
                {shown.map((r, idx) => (
                  <div key={r.id || `rev_${idx}`}>
                    <ReviewCard r={r} />
                  </div>
                ))}
              </div>

              {filteredReviews.length > visible && (
                <div className="text-center mt-12">
                  <button
                    onClick={() => setVisible((prev) => prev + 6)}
                    className="inline-flex items-center bg-white/90 border-2 border-purple-200 text-purple-950 font-bold uppercase tracking-wider text-xs px-8 py-4 rounded-full shadow-md hover:bg-purple-600 hover:text-white hover:border-purple-600 transition-all duration-300"
                    data-testid="reviews-load-more"
                  >
                    Load More Reviews <ArrowRight size={16} className="ml-2" />
                  </button>
                </div>
              )}
            </>
          )}
        </div>
      </section>

      {/* SUBMIT REVIEW SECTION */}
      <section className="bg-white py-20 md:py-28 relative overflow-hidden" data-testid="reviews-submit-section">
        <div className="max-w-3xl mx-auto px-6 md:px-12">
          <div className="text-center">
            <Reveal><SectionLabel className="block mb-3">Your Experience</SectionLabel></Reveal>
            <Reveal delay={0.05}>
              <h2 className="font-heading font-bold text-purple-950 text-4xl md:text-5xl tracking-tight mb-4">Share your feedback</h2>
            </Reveal>
            <Reveal delay={0.1}>
              <p className="text-purple-900/80 text-base sm:text-lg max-w-xl mx-auto font-medium">
                Just completed a VOKTAA session? Tell us what stayed with you. Your feedback inspires the next batch of students!
              </p>
            </Reveal>
          </div>

          <div className="card-purple bg-gradient-to-br from-purple-50/80 via-white to-purple-50/50 border-2 border-purple-100 p-8 md:p-12 rounded-3xl shadow-xl mt-10 relative overflow-hidden">
            {submitted ? (
              <div className="py-10 text-center" data-testid="review-success">
                <div className="w-16 h-16 mx-auto flex items-center justify-center bg-purple-100 rounded-full shadow-inner">
                  <CheckCircle2 size={36} className="text-purple-600" />
                </div>
                <h3 className="font-heading font-bold text-2xl text-purple-950 mt-6">Thank You!</h3>
                <p className="text-purple-950/80 font-medium mt-3 max-w-md mx-auto">
                  Your review has been saved to the database and is now live on the site.
                </p>
                <button
                  onClick={() => setSubmitted(false)}
                  className="mt-6 border-2 border-purple-600 text-purple-700 font-bold uppercase tracking-wider text-xs px-6 py-3 rounded-full hover:bg-purple-600 hover:text-white transition-all shadow-sm"
                >
                  Submit Another Review
                </button>
              </div>
            ) : (
              <form onSubmit={submit} className="space-y-5" data-testid="review-form">
                <div className="grid sm:grid-cols-2 gap-5">
                  <label className="block">
                    <span className="font-mono text-xs uppercase tracking-[0.15em] text-purple-950 font-bold block mb-2">Full Name *</span>
                    <input className="input-brand w-full px-4 py-3 text-purple-950 font-medium" placeholder="Your Name" value={form.name} onChange={set("name")} data-testid="review-name" />
                  </label>
                  <label className="block">
                    <span className="font-mono text-xs uppercase tracking-[0.15em] text-purple-950 font-bold block mb-2">Email *</span>
                    <input type="email" className="input-brand w-full px-4 py-3 text-purple-950 font-medium" placeholder="name@domain.com" value={form.email} onChange={set("email")} data-testid="review-email" />
                  </label>
                </div>

                <div className="grid sm:grid-cols-2 gap-5">
                  <label className="block">
                    <span className="font-mono text-xs uppercase tracking-[0.15em] text-purple-950 font-bold block mb-2">Phone / WhatsApp</span>
                    <input className="input-brand w-full px-4 py-3 text-purple-950 font-medium" placeholder="+91 98765 43210" value={form.phone} onChange={set("phone")} data-testid="review-phone" />
                  </label>
                  <label className="block">
                    <span className="font-mono text-xs uppercase tracking-[0.15em] text-purple-950 font-bold block mb-2">Role *</span>
                    <Select value={form.role} onValueChange={(v) => setForm((f) => ({ ...f, role: v }))}>
                      <SelectTrigger className="input-brand w-full px-4 py-3 h-auto rounded-xl text-purple-950 font-medium" data-testid="review-role">
                        <SelectValue placeholder="Select role" />
                      </SelectTrigger>
                      <SelectContent>
                        {ROLE_OPTIONS.map((r) => <SelectItem key={r} value={r}>{r}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </label>
                </div>

                <div className="grid sm:grid-cols-2 gap-5">
                  <label className="block">
                    <span className="font-mono text-xs uppercase tracking-[0.15em] text-purple-950 font-bold block mb-2">College / Organisation</span>
                    <input className="input-brand w-full px-4 py-3 text-purple-950 font-medium" placeholder="e.g. Engineering College Guntur" value={form.organisation} onChange={set("organisation")} data-testid="review-organisation" />
                  </label>
                  <label className="block">
                    <span className="font-mono text-xs uppercase tracking-[0.15em] text-purple-950 font-bold block mb-2">Programme Attended *</span>
                    <Select value={form.program} onValueChange={(v) => setForm((f) => ({ ...f, program: v }))}>
                      <SelectTrigger className="input-brand w-full px-4 py-3 h-auto rounded-xl text-purple-950 font-medium" data-testid="review-program">
                        <SelectValue placeholder="Select programme" />
                      </SelectTrigger>
                      <SelectContent>
                        {PROGRAM_OPTIONS.map((r) => <SelectItem key={r} value={r}>{r}</SelectItem>)}
                      </SelectContent>
                    </Select>
                  </label>
                </div>

                <div>
                  <span className="font-mono text-xs uppercase tracking-[0.15em] text-purple-950 font-bold block mb-2">Rating *</span>
                  <Stars value={form.rating} size={26} onChange={(v) => setForm((f) => ({ ...f, rating: v }))} testid="review-stars" />
                </div>

                <label className="block">
                  <span className="font-mono text-xs uppercase tracking-[0.15em] text-purple-950 font-bold block mb-2">Your Review *</span>
                  <textarea rows={4} className="input-brand w-full px-4 py-3 resize-none text-purple-950 font-medium" placeholder="What did you gain from the session? What would you tell someone considering VOKTAA training?" value={form.review} onChange={set("review")} data-testid="review-text" />
                </label>

                <button
                  type="submit"
                  disabled={submitting}
                  className="w-full inline-flex items-center justify-center bg-gradient-to-r from-purple-600 to-indigo-600 text-white font-bold uppercase tracking-wider text-xs px-8 py-4 rounded-full shadow-lg shadow-purple-500/25 hover:shadow-purple-500/40 hover:scale-[1.01] transition-all disabled:opacity-60"
                  data-testid="review-submit-button"
                >
                  {submitting ? "Submitting..." : "Submit Review"} <ArrowRight size={16} className="ml-2" />
                </button>
              </form>
            )}
          </div>
        </div>
      </section>
    </>
  );
};

export default Reviews;
