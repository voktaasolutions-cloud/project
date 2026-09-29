export const INITIAL_FALLBACK_REVIEWS = [
  { id: "r1", name: "Tejasri Penubothu", role: "Student", organisation: "Student", program: "Soft Skills Development", rating: 5, review: "I started using VOKTAA Solutions last week to improve my communication skills, leadership qualities, and interview skills. The training sessions are engaging, well-organized, and easy to understand. The trainers explain every concept clearly with practical examples, which has helped me build confidence. Whenever I had a question, the support team responded quickly and was very helpful. Overall, it has been a great learning experience, and I highly recommend VOKTAA Solutions to anyone looking to improve their soft skills.", status: "approved" },
  { id: "r2", name: "Sahithi Srinivas S", role: "Student", organisation: "Student", program: "Campus Recruitment Training", rating: 5, review: "I started using VOKTAA Solutions last week to fix my communication skills, leadership qualities and Interview Tips. The app is very clean and fast. When I had a question, their online/offline sessions helped my interviews and the support team replied in minutes. Highly recommend.", status: "approved" },
  { id: "r3", name: "N Venkata Bhargavi", role: "Student", organisation: "Student", program: "Communication Skills", rating: 5, review: "This session will definitely be useful for those who want to build a strong foundation on communication skills and also boost them with confidence to face the interviews. I learned a lot of tips which helped me in my interviews.", status: "approved" },
  { id: "r4", name: "Anumula Abhinaya", role: "Student", organisation: "Student", program: "Public Speaking & Debate", rating: 5, review: "The session was very useful and interactive. I learned many things that will help me improve my communication and confidence.", status: "approved" },
  { id: "r5", name: "VOKTAA Student", role: "Student", organisation: "Student", program: "Soft Skills & Communication", rating: 5, review: "I joined the program to improve my communication skills, but I gained much more than that. It helped me become more confident, improve my body language, and interact professionally with others.", status: "approved" },
  { id: "r6", name: "Kavya Gowripatnam", role: "Placement Officer", organisation: "Partner College", program: "Campus Placement & Soft Skills", rating: 5, review: "VOKTAA Solutions delivered exceptional CRT and soft skills modules for our batch. The interactive sessions boosted student confidence, interview readiness, and placement outcomes significantly.", status: "approved" }
];

const IGNORED_TEST_REVIEWS = new Set(["good", "nice", "test", "demo", "sample", "hii", "hello"]);

export function dedupeReviews(list) {
  if (!Array.isArray(list)) return [];
  const seen = new Set();
  return list.filter((r) => {
    if (!r) return false;
    const nameKey = (r.name || "").trim().toLowerCase();
    const reviewKey = (r.review || "").trim().toLowerCase();
    const key = `${nameKey}|${reviewKey}`;
    if (seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

function isRealReview(r) {
  if (!r || !r.review) return false;
  const cleaned = r.review.trim().toLowerCase().replace(/[^a-z0-9]/g, "");
  if (IGNORED_TEST_REVIEWS.has(cleaned)) return false;
  if (r.review.trim().length < 5) return false;
  return true;
}

export async function getPublicReviews() {
  try {
    const backendUrl = process.env.REACT_APP_BACKEND_URL || "";
    const res = await fetch(`${backendUrl}/api/reviews`);
    const contentType = res.headers.get("content-type") || "";
    if (res.ok && contentType.includes("application/json")) {
      const data = await res.json();
      if (Array.isArray(data)) {
        const real = data.filter(isRealReview);
        const combined = [...real, ...INITIAL_FALLBACK_REVIEWS];
        return dedupeReviews(combined);
      }
    }
  } catch (backendErr) {
    console.warn("Fetch backend reviews notice:", backendErr);
  }

  return dedupeReviews(INITIAL_FALLBACK_REVIEWS);
}

export async function submitReview(data) {
  const doc = {
    name: (data.name || "").slice(0, 250),
    email: (data.email || "").slice(0, 250),
    phone: (data.phone || "").slice(0, 50),
    role: (data.role || "Student").slice(0, 100),
    organisation: (data.organisation || "").slice(0, 250),
    program: (data.program || "").slice(0, 250),
    rating: Number(data.rating) || 5,
    review: (data.review || "").slice(0, 4500),
    status: data.status || "approved",
    timestamp: new Date().toISOString(),
  };

  const backendUrl = process.env.REACT_APP_BACKEND_URL || "";
  let res;

  try {
    res = await fetch(`${backendUrl}/api/reviews`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(doc),
    });
  } catch (netErr) {
    throw new Error(
      "Network connection error: Unable to connect to review service. Please try again later."
    );
  }

  const contentType = res.headers.get("content-type") || "";
  if (!contentType.includes("application/json")) {
    throw new Error(
      "API routing error: Backend returned non-JSON response. Ensure /api/ is routed to FastAPI backend."
    );
  }

  if (!res.ok) {
    const errJson = await res.json().catch(() => ({}));
    if (errJson.detail) {
      throw new Error(errJson.detail);
    }
    if (res.status === 422) {
      throw new Error("Invalid review submission. Please check all required fields.");
    } else if (res.status >= 500) {
      throw new Error("Server error saving review. Please try again later.");
    }
    throw new Error(`Failed to submit review (HTTP ${res.status}).`);
  }

  const resData = await res.json();
  return { id: resData.id || "rev_" + Date.now(), ...doc };
}

export async function getAllReviewsAdmin() {
  try {
    const backendUrl = process.env.REACT_APP_BACKEND_URL || "";
    const token = localStorage.getItem("voktaa_token");
    if (token) {
      const res = await fetch(`${backendUrl}/api/admin/reviews`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      const contentType = res.headers.get("content-type") || "";
      if (res.ok && contentType.includes("application/json")) {
        const data = await res.json();
        if (Array.isArray(data)) {
          const combined = [...data, ...INITIAL_FALLBACK_REVIEWS];
          return dedupeReviews(combined);
        }
      }
    }
  } catch (err) {
    console.warn("Fetch backend admin reviews notice:", err);
  }

  return dedupeReviews(INITIAL_FALLBACK_REVIEWS);
}

export async function updateReviewStatus(id, status) {
  const backendUrl = process.env.REACT_APP_BACKEND_URL || "";
  const token = localStorage.getItem("voktaa_token");
  if (token) {
    let res;
    try {
      res = await fetch(`${backendUrl}/api/admin/reviews/${id}`, {
        method: "PATCH",
        headers: {
          "Content-Type": "application/json",
          Authorization: `Bearer ${token}`,
        },
        body: JSON.stringify({ status }),
      });
    } catch (netErr) {
      throw new Error("Network error updating review status.");
    }

    if (!res.ok) {
      throw new Error("Failed to update review status.");
    }
  }
  return { id, status };
}

export async function deleteReview(id) {
  const backendUrl = process.env.REACT_APP_BACKEND_URL || "";
  const token = localStorage.getItem("voktaa_token");
  if (token) {
    let res;
    try {
      res = await fetch(`${backendUrl}/api/admin/reviews/${id}`, {
        method: "DELETE",
        headers: { Authorization: `Bearer ${token}` },
      });
    } catch (netErr) {
      throw new Error("Network error deleting review.");
    }

    if (!res.ok) {
      throw new Error("Failed to delete review.");
    }
  }
  return true;
}
