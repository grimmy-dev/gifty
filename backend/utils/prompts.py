"""System prompts and contact rendering for the pipeline."""

from utils.models import Contact

ANALYZE_SYS = (
    "You analyse professional contacts to prepare gift recommendations. For each contact: "
    "(1) extract strong signals (clearly evidenced interests/themes) and weak signals "
    "(plausible inferences); (2) write web search queries targeting real, purchasable gifts that "
    "fit the signals, occasion, budget, currency, and country. Modern search engines handle natural "
    "language well, so prefer clear intent-rich queries over terse keyword fragments.\n"
    "Never infer or use religion, politics, health, ethnicity, gender, or family status.\n"
    "GOOD signal: 'Cricket enthusiast (posts about matches)'. "
    "GOOD query: 'premium cricket coffee table book India under 5000 INR'.\n"
    "BAD signal: 'Likely Hindu' (religion), 'Has young kids' (family), 'Recovering from injury' (health). "
    "BAD query: 'cheap gift' (no signal, no country/budget).\n"
    "Return one analysis per contact, in the same order, echoing each contact's name."
)

VALIDATE_SYS = (
    "You validate candidate products for a professional gift. For each product decide if it is "
    "a real purchasable item relevant to the signals, within budget, sold to the contact's "
    "country, and appropriate for a professional relationship. Extract a price and store when "
    "present.\n"
    "GOOD: a product page on an in-country retailer, in budget, matching a signal -> relevant=true. "
    "BAD: a blog/listicle, an out-of-country store, out-of-budget, or anything personal/creepy "
    "(e.g. clothing sizes, fragrances) -> relevant=false."
)

RECOMMEND_SYS = (
    "You select the best professional gifts from validated candidates and write the notes. "
    "Pick the top 3 by relevance to signals, budget fit, and professional appropriateness. "
    "For each: explain why, state the signals used, give a confidence score and risk level, list "
    "assumptions, and write a short warm professional note (1-2 sentences, no emojis).\n"
    "GOOD note: 'Aarav, enjoyed our discovery call last week - thought this might resonate given "
    "your take on cricket and leadership.' "
    "BAD note: 'Hope you and the family love it!' (assumes family), or a generic 'Best wishes' "
    "(no personalisation).\n"
    "Lower confidence and state assumptions when signals are weak. Never invent products: use only "
    "the given candidates and their exact URLs."
)


BROADEN_SYS = (
    "Previous search queries returned too few valid products. Modern search engines handle natural "
    "language well, so write fuller intent-rich queries rather than keyword fragments - describe the "
    "person, the occasion, and what a good gift would be (e.g. 'thoughtful gift for a coffee-loving "
    "design lead in Germany around 60 euros'). Explore adjacent product categories and name well-known "
    "in-country retailers. Stay within the contact's country, currency, and budget, and avoid the exact "
    "phrasings that already failed."
)


def contact_summary(c: Contact) -> str:
    """Render a contact into a compact text block for prompting."""
    p = c.linkedin_profile
    g = c.gift_context
    exp = "; ".join(f"{e.title} at {e.company}: {e.description}" for e in p.experience)
    return (
        f"Name: {c.name}\nRole: {c.role} at {c.company}\nLocation: {c.location}\n"
        f"Headline: {p.headline}\nAbout: {p.about}\n"
        f"Experience: {exp}\n"
        f"Recent posts: {' | '.join(p.recent_posts)}\n"
        f"Recent comments: {' | '.join(p.recent_comments)}\n"
        f"Engaged topics: {', '.join(p.engaged_topics)}\n"
        f"Relationship: {c.relationship_context.relationship_type}; "
        f"{c.relationship_context.last_interaction}; goal: {c.relationship_context.business_goal}\n"
        f"Occasion: {g.occasion}\n"
        f"Budget: {g.budget_min}-{g.budget_max} {g.currency}, Country: {g.country}"
    )


def batch_summary(contacts: list[Contact]) -> str:
    """Render several contacts as a numbered block for one analyze call."""
    return "\n\n".join(
        f"[Contact {i + 1}]\n{contact_summary(c)}" for i, c in enumerate(contacts)
    )
