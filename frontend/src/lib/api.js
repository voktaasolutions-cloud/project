import { trackEvent, trackVisit, trackClick, getAnalyticsData } from "./events";
import { loginAdmin, logoutAdmin, getCurrentUser, isAuthenticated } from "./auth";
import { createEnquiry, getEnquiries } from "./enquiries";
import { getPublicReviews, submitReview, getAllReviewsAdmin, updateReviewStatus, deleteReview, INITIAL_FALLBACK_REVIEWS, dedupeReviews } from "./reviews";
import { getSiteSettings, updateSiteSettings } from "./settings";
import { uploadMedia, getMediaViewUrl, deleteMedia } from "./storage";
import {
  uploadKnowledgeDocument,
  getKnowledgeDocuments,
  toggleKnowledgeDocument,
  deleteKnowledgeDocument,
  searchKnowledgeBase
} from "./knowledgeBase";
import { getCommonConversationResponse } from "./commonConversation";
import { getSyllabusExpertResponse } from "./syllabusExpert";

export const CONTACT = {
  phone: "7416113199",
  phoneDisplay: "+91 74161 13199",
  whatsapp: "917416113199",
  email: "voktaasolutions@gmail.com",
  location: "Guntur, Andhra Pradesh, India",
  website: "www.voktaa.com",
  linkedin: "https://www.linkedin.com/in/voktaa-undefined-6331a8434/",
  instagram: "https://www.instagram.com/voktaasolutions/",
  facebook: "https://www.facebook.com/search/top?q=voktaa%20solutions",
};

// Re-export session helpers for backward compatibility
export const getToken = () => localStorage.getItem("voktaa_token");
export const setToken = (t) => localStorage.setItem("voktaa_token", t);
export const clearToken = () => {
  localStorage.removeItem("voktaa_token");
  logoutAdmin();
};

export function authHeaders() {
  const t = getToken();
  return t ? { Authorization: `Bearer ${t}` } : {};
}

// Re-export Appwrite services
export {
  trackEvent,
  trackVisit,
  trackClick,
  getAnalyticsData,
  loginAdmin,
  logoutAdmin,
  getCurrentUser,
  isAuthenticated,
  createEnquiry,
  getEnquiries,
  getPublicReviews,
  submitReview,
  getAllReviewsAdmin,
  updateReviewStatus,
  deleteReview,
  INITIAL_FALLBACK_REVIEWS,
  dedupeReviews,
  getSiteSettings,
  updateSiteSettings,
  uploadMedia,
  getMediaViewUrl,
  deleteMedia,
  uploadKnowledgeDocument,
  getKnowledgeDocuments,
  toggleKnowledgeDocument,
  deleteKnowledgeDocument,
  searchKnowledgeBase,
  getCommonConversationResponse,
  getSyllabusExpertResponse
};
