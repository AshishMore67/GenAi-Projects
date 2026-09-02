import os
os.environ["TRANSFORMERS_VERBOSITY"] = "error"

import streamlit as st
from dotenv import load_dotenv
from rag_pipeline import build_chain

load_dotenv()

SAMPLE_QUESTIONS = [
    "Why is my mobile internet so slow?",
    "My calls keep dropping — what should I do?",
    "How do I activate international roaming?",
    "Why is my bill higher than usual this month?",
    "My phone shows SIM not detected after a restart",
    "How do I enable Wi-Fi calling?",
    "I was charged for roaming but had a bundle active",
    "How do I unlock my phone for another network?",
]

st.set_page_config(
    page_title="Telecom Support Chat",
    page_icon="📡",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Styling (minimal, Streamlit-native + light CSS) ─────────────────────────
st.markdown("""
<style>
    :root {
        --tc-primary: #0F62FE;
        --tc-primary-dark: #0043CE;
        --tc-bg-soft: #F4F7FB;
        --tc-border: #E2E8F0;
    }

    /* Tighten default top padding, cap content width for readability */
    .block-container {
        max-width: 900px;
        padding-top: 1.5rem;
        padding-bottom: 3rem;
    }

    /* Header / brand banner */
    .tc-header {
        background: linear-gradient(135deg, var(--tc-primary) 0%, #2F80ED 100%);
        border-radius: 16px;
        padding: 1.6rem 2rem;
        color: white;
        margin-bottom: 1.75rem;
        box-shadow: 0 4px 18px rgba(15, 98, 254, 0.18);
    }
    .tc-header h1 {
        margin: 0;
        font-size: 1.5rem;
        font-weight: 700;
        letter-spacing: -0.01em;
    }
    .tc-header p {
        margin: 0.35rem 0 0 0;
        font-size: 0.92rem;
        opacity: 0.92;
    }
    .tc-badge {
        display: inline-block;
        background: rgba(255,255,255,0.16);
        border: 1px solid rgba(255,255,255,0.28);
        border-radius: 999px;
        padding: 0.15rem 0.7rem;
        font-size: 0.72rem;
        font-weight: 600;
        margin-top: 0.6rem;
        letter-spacing: 0.02em;
    }

    /* Sidebar branding */
    .tc-side-brand {
        display: flex;
        align-items: center;
        gap: 0.5rem;
        margin-bottom: 0.1rem;
    }
    .tc-side-brand span.icon { font-size: 1.4rem; }
    .tc-side-brand span.text {
        font-weight: 700;
        font-size: 1.05rem;
        color: #1A202C;
    }
    section[data-testid="stSidebar"] .stCaption, section[data-testid="stSidebar"] p {
        color: #64748B;
    }
    section[data-testid="stSidebar"] h4 {
        margin-bottom: 0.15rem;
    }

    /* Sample question buttons -> card-like */
    section[data-testid="stSidebar"] .stButton button {
        text-align: left;
        justify-content: flex-start;
        background: white;
        border: 1px solid var(--tc-border);
        border-radius: 10px;
        padding: 0.55rem 0.8rem;
        font-size: 0.85rem;
        color: #1A202C;
        white-space: normal;
        line-height: 1.3;
    }
    section[data-testid="stSidebar"] .stButton button:hover {
        border-color: var(--tc-primary);
        color: var(--tc-primary);
    }

    /* Clear conversation button distinct (danger-lite) */
    .tc-clear-btn button {
        background: #FFF5F5 !important;
        border: 1px solid #FED7D7 !important;
        color: #C53030 !important;
    }
    .tc-clear-btn button:hover {
        border-color: #C53030 !important;
        background: #FFEBEB !important;
    }

    /* Chat bubbles */
    div[data-testid="stChatMessage"] {
        border-radius: 14px;
        padding: 0.25rem 0.4rem;
        margin-bottom: 0.4rem;
    }
    div[data-testid="stChatMessageContent"] p {
        font-size: 0.95rem;
        line-height: 1.55;
    }

    /* Empty state / welcome card */
    .tc-empty {
        background: var(--tc-bg-soft);
        border: 1px solid var(--tc-border);
        border-radius: 16px;
        padding: 2.2rem 2rem;
        text-align: center;
        margin: 0.5rem 0 1.75rem 0;
    }
    .tc-empty h3 {
        margin: 0.6rem 0 0.3rem 0;
        font-size: 1.15rem;
        color: #1A202C;
    }
    .tc-empty p {
        color: #64748B;
        font-size: 0.9rem;
        margin: 0 auto;
        max-width: 480px;
    }
    .tc-empty .tc-emoji { font-size: 2rem; }

    .tc-topic-row {
        display: flex;
        flex-wrap: wrap;
        gap: 0.5rem;
        justify-content: center;
        margin-top: 1.1rem;
    }
    .tc-topic-chip {
        background: white;
        border: 1px solid var(--tc-border);
        border-radius: 999px;
        padding: 0.35rem 0.85rem;
        font-size: 0.78rem;
        color: #334155;
    }

    /* Responsive tweaks for small screens */
    @media (max-width: 640px) {
        .tc-header { padding: 1.2rem 1.3rem; border-radius: 12px; }
        .tc-header h1 { font-size: 1.2rem; }
        .tc-empty { padding: 1.6rem 1.2rem; }
        .block-container { padding-left: 0.8rem; padding-right: 0.8rem; }
    }
</style>
""", unsafe_allow_html=True)


@st.cache_resource
def get_chain():
    return build_chain()


if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_question" not in st.session_state:
    st.session_state.pending_question = None

# ── Sidebar ──────────────────────────────────────────────────────────────────
with st.sidebar:
    st.markdown(
        '<div class="tc-side-brand"><span class="icon">📡</span>'
        '<span class="text">Telecom Support</span></div>',
        unsafe_allow_html=True,
    )
    st.caption("Powered by RAG · Qwen3-32B on Groq")
    st.divider()

    st.markdown("#### 💡 Sample questions")
    st.caption("Tap one to send it instantly.")
    for q in SAMPLE_QUESTIONS:
        if st.button(q, use_container_width=True, key=f"sample_{q}"):
            st.session_state.pending_question = q

    st.divider()
    st.markdown('<div class="tc-clear-btn">', unsafe_allow_html=True)
    if st.button("🗑️ Clear conversation", use_container_width=True):
        st.session_state.messages = []
    st.markdown('</div>', unsafe_allow_html=True)

# ── Header ───────────────────────────────────────────────────────────────────
st.markdown("""
<div class="tc-header">
    <h1>📡 Customer Care Assistant</h1>
    <p>Ask about connectivity, billing, SIM, roaming, and more — answered instantly with AI-backed support.</p>
    <span class="tc-badge">● RAG-powered · Live</span>
</div>
""", unsafe_allow_html=True)

# ── Empty state (before first message) ──────────────────────────────────────
if not st.session_state.messages:
    st.markdown("""
    <div class="tc-empty">
        <div class="tc-emoji">👋</div>
        <h3>How can we help you today?</h3>
        <p>Type your question below or pick a sample topic from the sidebar to get started.</p>
        <div class="tc-topic-row">
            <span class="tc-topic-chip">📶 Network &amp; Connectivity</span>
            <span class="tc-topic-chip">💳 Billing &amp; Charges</span>
            <span class="tc-topic-chip">🌍 Roaming</span>
            <span class="tc-topic-chip">📱 SIM &amp; Device</span>
        </div>
    </div>
    """, unsafe_allow_html=True)

# ── Chat history ─────────────────────────────────────────────────────────────
for msg in st.session_state.messages:
    avatar = "🧑" if msg["role"] == "user" else "📡"
    with st.chat_message(msg["role"], avatar=avatar):
        st.markdown(msg["content"])

# Resolve question from chat input or sidebar button click
question = st.chat_input("Describe your issue…")
if st.session_state.pending_question:
    question = st.session_state.pending_question
    st.session_state.pending_question = None

if question:
    st.session_state.messages.append({"role": "user", "content": question})
    with st.chat_message("user", avatar="🧑"):
        st.markdown(question)

    with st.chat_message("assistant", avatar="📡"):
        chain = get_chain()
        response = st.write_stream(chain.stream(question))

    st.session_state.messages.append({"role": "assistant", "content": response})