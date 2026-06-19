"""Hadab Souk — Flask e-commerce app."""
from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
from catalog import PRODUCTS, CATEGORIES, get_product, get_category, by_category, related
from translations import TRANSLATIONS

app = Flask(__name__)
app.secret_key = "hadab-souk-change-this-secret-in-production"


@app.context_processor
def inject_globals():
    """Make lang, t, cart count available in every template."""
    lang = session.get("lang", "en")
    t = TRANSLATIONS[lang]
    cart = session.get("cart", {})
    cart_count = sum(cart.values())
    return {
        "lang": lang,
        "t": t,
        "dir": "rtl" if lang == "ar" else "ltr",
        "categories": CATEGORIES,
        "cart_count": cart_count,
        "name_field": "name_ar" if lang == "ar" else "name_en",
        "desc_field": "desc_ar" if lang == "ar" else "desc_en",
        "cat_name_field": "name_ar" if lang == "ar" else "name_en",
    }


@app.route("/set-lang/<lang>")
def set_lang(lang):
    if lang in ("en", "ar"):
        session["lang"] = lang
    return redirect(request.referrer or url_for("index"))


# ---------- Pages ----------
@app.route("/")
def index():
    featured = [p for p in PRODUCTS if p.get("featured")]
    best = [p for p in PRODUCTS if p.get("best_seller")]
    deals = [p for p in PRODUCTS if p.get("old_price")][:4]
    return render_template("index.html", featured=featured, best=best, deals=deals)


@app.route("/shop")
def shop():
    q = request.args.get("q", "").strip().lower()
    sort = request.args.get("sort", "featured")
    items = PRODUCTS[:]
    if q:
        items = [p for p in items if q in p["name_en"].lower() or q in p["name_ar"] or q in p["brand"].lower()]
    if sort == "low":
        items.sort(key=lambda p: p["price"])
    elif sort == "high":
        items.sort(key=lambda p: -p["price"])
    elif sort == "rating":
        items.sort(key=lambda p: -p["rating"])
    return render_template("shop.html", products=items, q=q, sort=sort)


@app.route("/category/<slug>")
def category(slug):
    cat = get_category(slug)
    if not cat:
        return render_template("404.html"), 404
    items = by_category(slug)
    return render_template("category.html", category=cat, products=items)


@app.route("/product/<slug>")
def product(slug):
    p = get_product(slug)
    if not p:
        return render_template("404.html"), 404
    return render_template("product.html", product=p, related=related(p))


# ---------- Cart ----------
@app.route("/cart")
def cart_view():
    cart = session.get("cart", {})
    items = []
    subtotal = 0
    for pid, qty in cart.items():
        p = next((x for x in PRODUCTS if x["id"] == pid), None)
        if p:
            line = p["price"] * qty
            subtotal += line
            items.append({"product": p, "qty": qty, "line": line})
    return render_template("cart.html", items=items, subtotal=subtotal)


@app.route("/cart/add/<pid>", methods=["POST"])
def cart_add(pid):
    qty = int(request.form.get("qty", 1))
    cart = session.get("cart", {})
    cart[pid] = cart.get(pid, 0) + qty
    session["cart"] = cart
    if request.headers.get("X-Requested-With") == "fetch":
        return jsonify({"count": sum(cart.values())})
    return redirect(url_for("cart_view"))


@app.route("/cart/update/<pid>", methods=["POST"])
def cart_update(pid):
    qty = int(request.form.get("qty", 1))
    cart = session.get("cart", {})
    if qty <= 0:
        cart.pop(pid, None)
    else:
        cart[pid] = qty
    session["cart"] = cart
    return redirect(url_for("cart_view"))


@app.route("/cart/remove/<pid>", methods=["POST"])
def cart_remove(pid):
    cart = session.get("cart", {})
    cart.pop(pid, None)
    session["cart"] = cart
    return redirect(url_for("cart_view"))


# ---------- Checkout ----------
@app.route("/checkout", methods=["GET", "POST"])
def checkout():
    cart = session.get("cart", {})
    items = []
    subtotal = 0
    for pid, qty in cart.items():
        p = next((x for x in PRODUCTS if x["id"] == pid), None)
        if p:
            subtotal += p["price"] * qty
            items.append({"product": p, "qty": qty})

    discount = 0
    coupon = request.form.get("coupon", "").strip().upper() if request.method == "POST" else ""
    if coupon == "HADAB10":
        discount = subtotal * 0.10
    shipping = 0 if subtotal >= 200 else 25
    total = subtotal - discount + shipping

    if request.method == "POST" and request.form.get("action") == "place":
        session["cart"] = {}
        flash(TRANSLATIONS[session.get("lang", "en")]["order_success"], "success")
        return redirect(url_for("index"))

    return render_template(
        "checkout.html",
        items=items, subtotal=subtotal, shipping=shipping,
        discount=discount, total=total, coupon=coupon,
    )


@app.route("/about")
def about():
    return render_template("about.html")


@app.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        flash("Thanks! We'll get back to you soon.", "success")
        return redirect(url_for("contact"))
    return render_template("contact.html")


# ---------- Chatbot ----------
@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json(silent=True) or {}
    msg = (data.get("message") or "").strip().lower()
    lang = session.get("lang", "en")
    ar = lang == "ar"

    def R(en, arabic):
        return arabic if ar else en

    if not msg:
        reply = R("Please type a message.", "الرجاء كتابة رسالة.")
    elif any(w in msg for w in ["hi", "hello", "hey", "salam", "سلام", "مرحبا", "اهلا"]):
        reply = R("Hello! 👋 Welcome to Hadab Souk. How can I help you today?",
                  "مرحباً! 👋 أهلاً بك في هَدَب سوق. كيف أستطيع مساعدتك؟")
    elif any(w in msg for w in ["ship", "deliver", "توصيل", "شحن"]):
        reply = R("🚚 Free shipping on orders over SAR 200. Standard delivery 2–5 days across the Gulf.",
                  "🚚 شحن مجاني للطلبات فوق ٢٠٠ ريال. التوصيل خلال ٢-٥ أيام في دول الخليج.")
    elif any(w in msg for w in ["return", "refund", "ارجاع", "استرداد"]):
        reply = R("↩️ Easy 14-day returns on all products. Just contact support to start a return.",
                  "↩️ يمكنك الإرجاع خلال ١٤ يوماً. تواصل مع الدعم لبدء عملية الإرجاع.")
    elif any(w in msg for w in ["pay", "payment", "card", "cod", "دفع", "بطاقة"]):
        reply = R("💳 We accept Visa, Mastercard, Mada, Apple Pay, and Cash on Delivery.",
                  "💳 نقبل فيزا، ماستركارد، مدى، آبل باي والدفع عند الاستلام.")
    elif any(w in msg for w in ["coupon", "discount", "promo", "خصم", "كوبون"]):
        reply = R("🎁 Use code HADAB10 at checkout to get 10% off your order!",
                  "🎁 استخدم كود HADAB10 عند الدفع للحصول على خصم ١٠٪!")
    elif any(w in msg for w in ["warranty", "ضمان"]):
        reply = R("🛡 All flagship products come with a 2-year warranty. Authentic, region-supported devices only.",
                  "🛡 جميع المنتجات الرئيسية تأتي بضمان سنتين. أجهزة أصلية ومدعومة.")
    elif any(w in msg for w in ["contact", "support", "help", "دعم", "مساعدة"]):
        reply = R("📞 Reach us at +966 800 123 4567 or support@hadabsouk.com — 24/7.",
                  "📞 تواصل معنا على +966 800 123 4567 أو support@hadabsouk.com — ٢٤/٧.")
    elif any(w in msg for w in ["iphone", "phone", "smartphone", "هاتف", "ايفون"]):
        reply = R("📱 Check our Smartphones category — latest iPhone, Samsung, and more in stock!",
                  "📱 تصفح قسم الهواتف الذكية — أحدث آيفون وسامسونج متوفرة!")
    elif any(w in msg for w in ["laptop", "macbook", "لابتوب"]):
        reply = R("💻 Premium laptops from Apple, Dell, and more in our Laptops category.",
                  "💻 لابتوبات فاخرة من آبل وديل في قسم اللابتوب.")
    elif any(w in msg for w in ["thanks", "thank", "شكرا"]):
        reply = R("You're welcome! Happy shopping at Hadab Souk 🛍",
                  "العفو! تسوق ممتع في هَدَب سوق 🛍")
    else:
        reply = R("I can help with shipping, returns, payments, discounts, warranty, or finding products. What would you like to know?",
                  "أستطيع مساعدتك في الشحن، الإرجاع، الدفع، الخصومات، الضمان، أو إيجاد المنتجات. ماذا تريد أن تعرف؟")

    return jsonify({"reply": reply})


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404


if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0", port=5000)
