from typing import Optional
import os
import sqlite3
from dotenv import load_dotenv
from langchain.agents import create_agent
from langchain.tools import tool
from langchain_core.messages import HumanMessage
from langchain_groq import ChatGroq
import json
import base64
from reviews_api import get_product_rating

load_dotenv()

DB_PATH = os.path.join(os.path.dirname(__file__),"store.db")


#single user local assitant
USER_ID = "default_user"

llm = ChatGroq(model= "openai/gpt-oss-120b", temperature=0)
vision_llm = ChatGroq(model="qwen/qwen3.8-27b", temperature= 0)

# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------

@tool
def search_product(query: str, max_price:Optional[float] = None, is_organic: Optional[bool] = None) -> str:
    """
    Search the product database by keyword (matched against name, description, and category).
    Optionally filter by maximum price and/or organic status.
    Returns a JSON array of matching products, each with: id, name, category, price,
    description, is_organic.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    sql = "SELECT id, name, category, price, description, is_organic FROM products WHERE 1=1"
    params: list = []

    if query:
        sql += " AND (name LIKE ? OR description LIKE ? OR category LIKE ?)"
        like = f"%{query}%"
        params.extend([like, like, like])

    if max_price is not None:
        sql += " AND price <= ?"
        params.append(max_price)

    if is_organic is not None:
        sql += " AND is_organic = ?"
        params.append(1 if is_organic else 0)

    cursor.execute(sql, params)
    rows = cursor.fetchall()
    conn.close()

    products = [
        {
            "id":          row[0],
            "name":        row[1],
            "category":    row[2],
            "price":       row[3],
            "description": row[4],
            "is_organic":  bool(row[5]),
        }
        for row in rows
    ]
    return json.dumps(products)

@tool
def get_rating(product_id: int)-> str:
    """
    Get the average customer rating and total review count for a product by its ID.
    Returns a JSON object with: product_id, average_rating, review_count.
    """
    result = get_product_rating(product_id)
    return json.dumps(result)

@tool
def checkout(product_id: int)-> str:
    """
    Place an order for the given product ID. Saves the order to the database and returns
    a confirmation message with the order ID, product name, and price.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name, price FROM products WHERE id = ?", (product_id,))
    row = cursor.fetchone()

    if not row:
        conn.close()
        return f"Error: product with ID {product_id} not found"

    name, price = row
    cursor.execute(
        "INSERT INTO orders (product_id, product_name, price, user_id) VALUES (?, ?, ?, ?)",
        (product_id, name, price, USER_ID),
    )
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()

    return (
        f"Order #{order_id} confirmed! '{name}' has been successfully ordered for ${price:.2f}. "
        f"Your order will arrive in 3-5 business days. Thank you for shopping with us!"
    )

@tool
def describe_product_image(image_path: str) -> str:
    """
    Analyze a product image and return its key attributes as a JSON object.
    Use this when the user uploads a photo of a product they are interested in.
    The returned attributes can be used directly with search_products.
    """
    with open(image_path, "rb") as f:
        image_data = base64.b64encode(f.read()).decode()

    ext = os.path.splitext(image_path)[1].lower().lstrip(".")
    mime = "image/jpeg" if ext in ("jpg", "jpeg") else f"image/{ext}"

    message = HumanMessage(content=[
        {
            "type": "image_url",
            "image_url": {"url": f"data:{mime};base64,{image_data}"},
        },
        {
            "type": "text",
            "text": (
                "Look at this product image and extract its key attributes. "
                "Return ONLY a JSON object with these fields:\n"
                "- product_type: what kind of product it is (e.g. honey, olive oil, almonds)\n"
                "- search_query: a short keyword to search for it (e.g. 'honey', 'olive oil')\n"
                "- is_organic: true if the label says organic, false if not, null if unclear\n"
                "- description: one sentence describing the product"
            ),
        },
    ])

    response = vision_llm.invoke([message])
    return response.content

@tool
def get_order_history(limit: int = 10)-> str:
    """
    Get the current user's past orders, most recent first.
    Returns a JSON array of orders, each with: order_id, product_id, product_name, price, ordered_at.
    Use this to answer questions like "what have I ordered before?" or "did I already buy X?".
    Do NOT use search_products for these questions
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
         """
        SELECT id, product_id, product_name, price, ordered_at
        FROM orders WHERE user_id = ? ORDER BY ordered_at DESC LIMIT ?
        """,
        (USER_ID, limit),
    )
    rows = cursor.fetchall()
    conn.close()

    orders = [
        {
            "order_id":     row[0],
            "product_id":   row[1],
            "product_name": row[2],
            "price":        row[3],
            "ordered_at":   row[4],
        }
        for row in rows
    ]
    return json.dumps(orders)

@tool
def get_preferences() -> str:
    """
    Get the current user's saved shopping preferences.
    Returns a JSON object: {prefers_organic, max_price}. Either field may be null if never set.
    Call this once at the start of a BROWSING request so saved preferences can be applied
    automatically when the user doesn't repeat them in the current message.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
        "SELECT prefers_organic, max_price FROM preferences WHERE user_id = ?", (USER_ID,)
    )
    row = cursor.fetchone()
    conn.close()

    if not row:
        return json.dumps({"prefers_organic": None, "max_price": None})

    return json.dumps({
        "prefers_organic": bool(row[0]) if row[0] is not None else None,
        "max_price": row[1],
    })

@tool
def update_preferences(prefers_organic: Optional[bool] = None, max_price: Optional[float] = None) -> str:
    """
    Save or update the current user's standing shopping preferences.
    Only pass a field when the user actually stated a lasting preference, e.g.:
    "I always want organic" -> prefers_organic=True
    "never show me anything over $20" -> max_price=20
    Leave a field as None to keep its previously saved value unchanged. Do NOT call this
    for a one-off filter mentioned for a single search only.
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute(
            "SELECT prefers_organic, max_price FROM preferences WHERE user_id = ?", (USER_ID,)
        )
    row = cursor.fetchone()
    existing_organic, existing_max = row if row else (None, None)
    new_organic = existing_organic if prefers_organic is None else (1 if prefers_organic else 0)
    new_max = existing_max if max_price is None else max_price
    
    cursor.execute(
        """
        INSERT INTO preferences (user_id, prefers_organic, max_price, updated_at)
        VALUES (?, ?, ?, datetime('now'))
        ON CONFLICT(user_id) DO UPDATE SET
            prefers_organic = excluded.prefers_organic,
            max_price       = excluded.max_price,
            updated_at      = excluded.updated_at
        """,
        (USER_ID, new_organic, new_max),
    )
    conn.commit()
    conn.close()
    return "Preferences saved."





# ---------------------------------------------------------------------------
# Agent
# ---------------------------------------------------------------------------

agent = create_agent(
    tools = [search_product,get_rating,checkout,describe_product_image,get_order_history,get_preferences,update_preferences],
    model = llm,
    system_prompt = (
        "You are a helpful shopping assistant. Follow these rules strictly.\n\n"
        "IMAGE SEARCH — when the user provides an image path:\n"
        "1. Call describe_product_image with the path to identify the product.\n"
        "2. Use the returned search_query and is_organic to call search_products.\n"
        "3. Continue with the BROWSING flow from step 2 onwards.\n\n"
        "MEMORY — preferences and order history:\n"
        "1. At the start of a BROWSING request, call get_preferences once. If the user's\n"
        "   current message does not state an organic preference or a max price, apply the\n"
        "   saved values as default filters for this search. If the current message DOES\n"
        "   state a filter, that overrides the saved preference for this search only.\n"
        "2. If the user states a standing preference (e.g. 'I always want organic',\n"
        "   'never show me anything over $20', 'stop showing me non-organic stuff'), call\n"
        "   update_preferences to save it, briefly confirm it's saved, then continue with\n"
        "   whatever else they asked for.\n"
        "3. If the user asks about past orders ('what have I ordered before', 'did I already\n"
        "   buy honey', 'show my order history'), call get_order_history and answer directly\n"
        "   in plain text. Do not call search_products for this.\n\n"
        "BROWSING — when the user describes what they want to buy:\n"
        "1. Call search_products to find matching items (apply any price/organic filters given).\n"
        "   or, per MEMORY step 1, saved preferences).\n"
        "2. For each candidate, call get_rating to retrieve its average rating.\n"
        "3. Filter by the user's minimum rating if specified.\n"
        "4. Present qualifying products as a numbered list. For each item use this exact format "
        "   (plain text, no backticks, no code blocks, no bold, no italic):\n\n"
        "   #<number>. <name> (ID:<product_id>) — $<price> ★<rating> — <organic or non-organic>\n\n"
        "   Add a blank line between each product entry for readability. "
        "   Always include (ID:X) so you can reference it later.\n"
        "5. If only one product qualifies, still show it in the list and ask: "
        "   'Would you like to order it? Just say yes or give me the number.'\n"
        "6. Do NOT call checkout at this stage.\n\n"
        "ORDERING — when the user confirms they want to buy (e.g. 'yes', 'sure', 'go ahead', "
        "'order number 2', 'the first one', 'get me #3'):\n"
        "1. Look at your previous message to find the (ID:X) for the chosen product "
        "   (if only one was listed and the user says 'yes', use that product's ID).\n"
        "2. Call checkout with that product_id (the number from (ID:X)).\n"
        "3. Confirm the order to the user in plain text.\n\n"
        "Never place an order unless the user explicitly confirms. "
        "Never guess a product_id — always take it from the (ID:X) in your own previous message."
    ),
)


if __name__ == "__main__":
    image_path = os.path.join("resources", "honey.png")
    response = describe_product_image(image_path)
    print(response)
    # result = agent.invoke(
    #     {
    #         "messages": [
    #             {
    #                 "role": "user",
    #                 "content": (
    #                     "I want to buy Oats "
    #                 ),
    #             }
    #         ]
    #     }
    # )
    # print(result["messages"][-1].content)
