import os
import re
import tempfile

import streamlit as st

from shopping_agent import agent

# ---------------------------------------------------------------------------
# Page config
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="ShopBot — AI Shopping Assistant",
    page_icon="🛒",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# Theme / CSS — storefront look (Amazon/Flipkart-style header, card grid)
# ---------------------------------------------------------------------------
st.markdown(
    """
    <style>
        #MainMenu, footer {visibility: hidden;}

        .stApp {
            background: #f5f7fa;
        }

        .storefront-header {
            background: linear-gradient(90deg, #131921 0%, #232f3e 100%);
            padding: 22px 32px;
            border-radius: 12px;
            margin-bottom: 18px;
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .storefront-header h1 {
            color: #ffffff;
            font-size: 28px;
            margin: 0;
            font-weight: 700;
        }
        .storefront-header p {
            color: #d5d9d9;
            margin: 4px 0 0 0;
            font-size: 14px;
        }
        .storefront-badge {
            background: #febd69;
            color: #131921;
            padding: 6px 14px;
            border-radius: 20px;
            font-size: 13px;
            font-weight: 700;
        }

        section[data-testid="stSidebar"] {
            background: #ffffff;
            border-right: 1px solid #e6e6e6;
        }
        section[data-testid="stSidebar"] h2 {
            color: #131921;
            font-size: 18px;
        }

        div[data-testid="stChatMessage"] {
            background: #ffffff;
            border-radius: 14px;
            padding: 6px 4px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.06);
            margin-bottom: 6px;
        }

        .product-grid {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(230px, 1fr));
            gap: 14px;
            margin: 10px 0 16px 0;
        }
        .product-card {
            background: #ffffff;
            border: 1px solid #e6e6e6;
            border-radius: 14px;
            padding: 16px;
            transition: box-shadow 0.15s ease, transform 0.15s ease;
        }
        .product-card:hover {
            box-shadow: 0 6px 16px rgba(0,0,0,0.10);
            transform: translateY(-2px);
        }
        .product-name {
            font-weight: 700;
            font-size: 15px;
            color: #0f1111;
            margin-bottom: 6px;
            min-height: 38px;
        }
        .product-price {
            color: #b12704;
            font-size: 19px;
            font-weight: 700;
        }
        .product-rating {
            color: #e67e22;
            font-size: 13px;
            margin: 4px 0 8px 0;
        }
        .product-tag {
            display: inline-block;
            font-size: 11px;
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 10px;
            margin-bottom: 8px;
        }
        .tag-organic { background: #e6f4ea; color: #1e7e34; }
        .tag-regular { background: #eef1f4; color: #555; }

        div[data-testid="stChatInput"] textarea {
            border-radius: 10px !important;
        }

        .stButton > button {
            border-radius: 8px;
            font-weight: 600;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="storefront-header">
        <div>
            <h1>🛒 ShopBot</h1>
            <p>Your AI-powered personal shopper — search, compare, and order in one chat.</p>
        </div>
        <div class="storefront-badge">⚡ Live Assistant</div>
    </div>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# Cached agent — load / import once per server process, not per rerun
# ---------------------------------------------------------------------------
@st.cache_resource(show_spinner=False)
def get_agent():
    return agent


shopping_agent = get_agent()

# ---------------------------------------------------------------------------
# Product card parsing/rendering
# ---------------------------------------------------------------------------
PRODUCT_LINE_RE = re.compile(
    r"#(\d+)\.\s*(.+?)\s*\(ID:\s*(\d+)\)\s*—\s*\$([\d.]+)\s*★([\d.]+|N/?A)\s*—\s*(organic|non-organic)",
    re.IGNORECASE,
)


def extract_products(text: str):
    return PRODUCT_LINE_RE.findall(text)


def render_message(text: str, key_prefix: str = ""):
    """Render assistant text; draw a product card grid if a product list is detected,
    plus any surrounding prose."""
    products = extract_products(text)
    if not products:
        st.markdown(text.replace("$", r"\$"))
        return

    # Text before/after the product list (intro / follow-up question)
    remainder = PRODUCT_LINE_RE.sub("", text).strip()
    remainder = re.sub(r"\n{2,}", "\n\n", remainder).strip()

    lines = [ln for ln in text.splitlines() if ln.strip()]
    intro_lines = []
    for ln in lines:
        if PRODUCT_LINE_RE.search(ln):
            break
        intro_lines.append(ln)
    if intro_lines:
        st.markdown(" ".join(intro_lines).replace("$", r"\$"))

    cards_html = '<div class="product-grid">'
    for num, name, pid, price, rating, organic in products:
        tag_class = "tag-organic" if organic.lower() == "organic" else "tag-regular"
        rating_display = "No ratings yet" if rating.upper().replace("/", "") == "NA" else f"★ {rating} / 5"
        cards_html += f"""
            <div class="product-card">
                <span class="product-tag {tag_class}">{organic.title()}</span>
                <div class="product-name">#{num}. {name}</div>
                <div class="product-price">${price}</div>
                <div class="product-rating">{rating_display}</div>
            </div>
        """
    cards_html += "</div>"
    st.markdown(cards_html, unsafe_allow_html=True)

    # Quick-order buttons (send the same text a user would type)
    cols = st.columns(len(products))
    for i, (num, name, pid, price, rating, organic) in enumerate(products):
        with cols[i]:
            if st.button(f"Order #{num}", key=f"{key_prefix}_order_{pid}_{num}", use_container_width=True):
                queue_user_message(f"Order number {num}")
                st.rerun()

    trailing = remainder
    for num, name, pid, price, rating, organic in products:
        pass
    if trailing and not trailing.strip().startswith("#"):
        st.markdown(trailing.replace("$", r"\$"))


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "messages" not in st.session_state:
    st.session_state.messages = []  # [{role, content, display?}]
if "awaiting_response" not in st.session_state:
    st.session_state.awaiting_response = False


def queue_user_message(content: str, display: str = None):
    """Append a user message and mark that the agent needs to respond next run.
    Never invokes the agent directly here — avoids double-invocation on rerun."""
    st.session_state.messages.append(
        {"role": "user", "content": content, "display": display or content}
    )
    st.session_state.awaiting_response = True


# ---------------------------------------------------------------------------
# Sidebar — shop by image
# ---------------------------------------------------------------------------
with st.sidebar:
    st.header("📷 Shop by Image")
    st.caption("Upload a product photo and I'll find matching items in the store.")

    uploaded_file = st.file_uploader(
        "Upload product image", type=["jpg", "jpeg", "png", "webp"], label_visibility="collapsed"
    )

    if uploaded_file:
        st.image(uploaded_file, use_container_width=True)

    find_disabled = st.session_state.awaiting_response
    if uploaded_file and st.button(
        "🔍 Find similar products", use_container_width=True, disabled=find_disabled
    ):
        suffix = os.path.splitext(uploaded_file.name)[1] or ".jpg"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(uploaded_file.getvalue())
            image_path = tmp.name

        prompt = (
            "I uploaded a product image. Please analyze it and find similar products "
            f"in the store. Image path: {image_path}"
        )
        queue_user_message(prompt, display=f"📷 Searching by image: **{uploaded_file.name}**")
        st.rerun()

    st.divider()
    st.caption("💡 Try: *\"organic honey under $15 with 4+ rating\"*")

    if st.session_state.messages and st.button("🗑️ Clear conversation", use_container_width=True):
        st.session_state.messages = []
        st.session_state.awaiting_response = False
        st.rerun()

# ---------------------------------------------------------------------------
# Chat history
# ---------------------------------------------------------------------------
for idx, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        if msg["role"] == "user":
            st.markdown(msg.get("display", msg["content"]))
        else:
            render_message(msg["content"], key_prefix=f"hist_{idx}")

# ---------------------------------------------------------------------------
# Single point of agent invocation — runs at most once per new user message
# ---------------------------------------------------------------------------
if st.session_state.awaiting_response:
    with st.chat_message("assistant"):
        with st.spinner("Thinking…"):
            result = shopping_agent.invoke({"messages": st.session_state.messages})
            response = result["messages"][-1].content.replace("`", "")
        render_message(response, key_prefix=f"live_{len(st.session_state.messages)}")

    st.session_state.messages.append({"role": "assistant", "content": response})
    st.session_state.awaiting_response = False
    st.rerun()

# ---------------------------------------------------------------------------
# Chat input
# ---------------------------------------------------------------------------
if prompt := st.chat_input(
    "e.g. I want organic honey under $15 with 4+ rating",
    disabled=st.session_state.awaiting_response,
):
    queue_user_message(prompt)
    st.rerun()