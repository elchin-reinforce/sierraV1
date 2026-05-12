"""Deterministic scripted user simulator."""
from __future__ import annotations
import re
from typing import Any

from .base import BaseUser

# Per-task conversation scripts.  Each entry is a list of user turns.
# The scripted user pops them in order; when exhausted it sends ###STOP###.
_TASK_SCRIPTS: dict[str, list[str]] = {
    # Script structure (most tasks):
    #  0  → start() — opening request
    #  1  → respond() #1 — after agent asks for auth
    #  2  → respond() #2 — after agent confirms identity ("How can I help?")
    #  3  → respond() #3 — after agent proposes action ("Shall I proceed?")
    #  4+ → after write action(s) complete — fallback handles STOP
    "retail_task_001": [
        "Hi, I'd like to cancel my order #W4082615 because I ordered it by mistake.",
        "My email is mei.patel@example.com.",
        "I need to cancel order #W4082615. The reason is that I ordered it by mistake.",
        "Yes, please go ahead and cancel it.",
    ],
    "retail_task_002": [
        "Hello, I'd like to return the jeans from my delivered order #W7382910.",
        "My email is yusuf.rossi@example.com.",
        "I want to return the item in order #W7382910 and refund to credit_card_5421098.",
        "Yes, please process the return.",
    ],
    "retail_task_003": [
        "Hi, I want to exchange the t-shirt in order #W1937482. I have item_tshirt_s_red and want item_tshirt_m_blue instead.",
        "My email is sofia.chen@example.com.",
        "Exchange item_tshirt_s_red for item_tshirt_m_blue in order #W1937482. Use credit_card_3847291 for payment.",
        "Yes, please proceed with the exchange.",
    ],
    "retail_task_004": [
        "I need to change the shipping address for my pending order #W5849302 to 789 Pine Ave, Austin, TX 78702, USA.",
        "My email is marcus.johnson@example.com.",
        "The new address for order #W5849302 is: 789 Pine Ave, Austin, TX 78702, USA. Address line 2 is empty.",
        "Yes, please update the address.",
    ],
    "retail_task_005": [
        "I'd like to update my profile address to 456 Maple St, Seattle, WA 98102, USA.",
        "My email is aisha.williams@example.com.",
        "My new profile address is: 456 Maple St, Seattle, WA 98102, USA. No address line 2.",
        "Yes, go ahead and update it.",
    ],
    "retail_task_006": [
        "I want to change the headphones in my pending order #W6172839 from item_headphones_black_pro to item_headphones_black_standard.",
        "My email is noah.garcia@example.com.",
        "Change item_headphones_black_pro to item_headphones_black_standard in order #W6172839. Refund to credit_card_1029384.",
        "Yes, please make that change.",
    ],
    "retail_task_007": [
        "Hi, I need two things: cancel order #W3948201 (no longer needed) AND change the address on order #W8192034 to 100 Congress Ave, Boston, MA 02102, USA.",
        "My email is priya.sharma@example.com.",
        "Please cancel #W3948201 (reason: no longer needed) and change address on #W8192034 to 100 Congress Ave, Boston, MA 02102, USA.",
        "Yes, please cancel order #W3948201.",
        "Yes, and update the address for #W8192034 to 100 Congress Ave, Boston, MA 02102, USA.",
        "Yes, please proceed with the address change.",
    ],
    "retail_task_008": [
        "I'd like to cancel my order #W2948301.",
        "My email is liam.nguyen@example.com.",
        "I understand. Can you transfer me to a human agent or explain what I can do?",
    ],
    "retail_task_009": [
        "Can you tell me the price difference between Wireless Headphones Pro (Black) and Wireless Headphones Standard (Black)?",
        "My email is emma.kim@example.com.",
        "Great, please look up the product details and tell me the exact price difference.",
    ],
    "retail_task_010": [
        "I'd like to exchange all 3 water bottles from order #W7392841 for black 24oz ones (item_waterbottle_black_24oz).",
        "My email is carlos.martin@example.com.",
        "Exchange all three in order #W7392841: replace item_waterbottle_blue_24oz, item_waterbottle_red_24oz, item_waterbottle_green_24oz each with item_waterbottle_black_24oz. Use credit_card_4839201.",
        "Yes, please exchange all three at once.",
    ],
    "retail_task_011": [
        "Hi, I'd like to return the phone case from my delivered order #W2104411. I'd rather not share my email.",
        "My full name is Olivia Brown and my ZIP is 30301.",
        "Please return item_phonecase_clear from order #W2104411 and refund to paypal_5563728.",
        "Yes, please process the return.",
    ],
    "retail_task_012": [
        "I need to cancel my pending order #W2104412 — it's no longer needed.",
        "My email is jin.park@wrong.com.",
        "Sorry, my correct email is jin.park@example.com.",
        "Please cancel order #W2104412 (reason: no longer needed).",
        "Yes, please go ahead and cancel.",
    ],
    "retail_task_013": [
        "I'd like to change the payment method on my pending order #W2104413.",
        "My email is nina.petrov@example.com.",
        "Please change the payment method on order #W2104413 to credit_card_8855221.",
        "Yes, please proceed.",
    ],
    "retail_task_014": [
        "I want to upgrade both t-shirts in my pending order #W2104414 to large size.",
        "My email is fatima.alvarez@example.com.",
        "Change item_tshirt_s_red and item_tshirt_m_red in order #W2104414 to item_tshirt_l_red and item_tshirt_l_red. Use credit_card_7799334 for the price difference.",
        "Yes, please make that change.",
    ],
    "retail_task_015": [
        "I'd like to return the watch from my delivered order #W2104415. I want the refund on my gift card.",
        "My email is sofia.chen@example.com.",
        "Return item_watch_classic_metal from order #W2104415 and refund to gift_card_7291034.",
        "Yes, please process the return.",
    ],
    "retail_task_016": [
        "I want to return both water bottles in my delivered order #W2104416.",
        "My email is david.okonkwo@example.com.",
        "Return item_waterbottle_red_24oz and item_waterbottle_blue_24oz from order #W2104416. Refund to credit_card_1100221.",
        "Yes, please process the return.",
    ],
    "retail_task_017": [
        "I'd like to exchange the wallet in my delivered order #W2104417 for a cheaper variant.",
        "My email is olivia.brown@example.com.",
        "Exchange item_wallet_brown_full for item_wallet_brown_genuine in order #W2104417. Refund the difference to paypal_5563728.",
        "Yes, please proceed with the exchange.",
    ],
    "retail_task_018": [
        "I'd like to exchange the laptop in order #W2104418.",
        "My email is fatima.alvarez@example.com.",
        "I want to exchange item_laptop_16_512 in order #W2104418. Please look it up.",
        "I understand — what are my options?",
    ],
    "retail_task_019": [
        "I'd like to change item_sunglass_aviator_gold in my pending order #W2104419 to item_tshirt_m_blue.",
        "My email is nina.petrov@example.com.",
        "Please change item_sunglass_aviator_gold to item_tshirt_m_blue in order #W2104419. Use credit_card_8855221.",
        "Yes, please proceed.",
    ],
    "retail_task_020": [
        "I'd like to return the hair dryer from my delivered order #W2104420.",
        "My email is david.okonkwo@example.com.",
        "Return item_hairdryer_black_1500w from order #W2104420 and refund to credit_card_1100221. Please tell me the exact refund amount.",
        "Yes, please process the return.",
    ],
    "retail_task_021": [
        "Can you tell me the status of my order #W2104421?",
        "My email is jin.park@example.com.",
        "What is the current status of order #W2104421?",
    ],
    "retail_task_022": [
        "I need two things: cancel order #W8294031 (no longer needed) AND change the yoga mat in order #W2104422 from item_yoga_blue_6mm to item_yoga_green_8mm using gift_card_1938472.",
        "My email is emma.kim@example.com.",
        "Please cancel #W8294031 (no longer needed) and change item_yoga_blue_6mm to item_yoga_green_8mm in order #W2104422 using gift_card_1938472.",
        "Yes, please cancel order #W8294031.",
        "Yes, and please change the yoga mat in #W2104422 from item_yoga_blue_6mm to item_yoga_green_8mm using gift_card_1938472.",
        "Yes, please proceed with the change.",
    ],
    "retail_task_023": [
        "I moved and need to update both my profile address AND the shipping address of my pending order #W2104423 to: 222 Marietta St, Atlanta, GA 30303, USA.",
        "My email is olivia.brown@example.com.",
        "Please update my profile address to 222 Marietta St, Atlanta, GA 30303, USA. No address line 2.",
        "Yes, please update my profile address.",
        "Now also update the shipping address for order #W2104423 to 222 Marietta St, Atlanta, GA 30303, USA.",
        "Yes, please update the order address too.",
    ],
    "retail_task_024": [
        "I'd like to return only the clear phone case from my delivered order #W2104424. Keep the other two cases.",
        "My email is david.okonkwo@example.com.",
        "Return only item_phonecase_clear from order #W2104424 and refund to paypal_3322110.",
        "Yes, please process the partial return.",
    ],
    "retail_task_025": [
        "I'd like to exchange the blue phone case in my delivered order #W2104425 for the black variant.",
        "My email is nina.petrov@example.com.",
        "Exchange item_phonecase_blue for item_phonecase_black in order #W2104425. Use credit_card_8855221.",
        "Yes, please proceed with the exchange.",
    ],
}

_GENERIC_AUTH_RESPONSES = [
    "I just told you my email. Please check your previous messages.",
    "I'd like to continue. Can we proceed?",
    "Yes, please go ahead.",
    "Thank you, that's all I needed.",
]

_CONFIRM_KEYWORDS = re.compile(
    r"\b(confirm|proceed|shall i|should i|do you want|would you like|go ahead|approve)\b",
    re.IGNORECASE,
)
_AUTH_KEYWORDS = re.compile(
    r"\b(email|name|zip|authenticate|verify|identity|account)\b",
    re.IGNORECASE,
)


class ScriptedUser(BaseUser):
    """Uses a pre-defined message list per task, falling back to generic responses."""

    def __init__(self, task_id: str):
        self.task_id = task_id
        self._queue = list(_TASK_SCRIPTS.get(task_id, []))
        self._fallback_idx = 0
        self._started = False

    def start(self, instruction: str) -> str:
        self._started = True
        if self._queue:
            return self._queue.pop(0)
        return self._extract_opening(instruction)

    def respond(self, agent_message: str, history: list[dict[str, Any]]) -> str:
        if self._queue:
            return self._queue.pop(0)
        # Generic fallback: try to detect what the agent is asking for
        lower = agent_message.lower()
        if any(kw in lower for kw in ["cancelled", "cancellation", "updated", "returned", "exchanged", "done", "complete", "modified", "transferred", "has been", "have been", "successfully", "couldn't", "cannot", "could not", "status"]):
            return "###STOP###"
        if _AUTH_KEYWORDS.search(agent_message):
            return "I've already provided my information. Please proceed."
        if _CONFIRM_KEYWORDS.search(agent_message):
            return "Yes, please proceed."
        # Generic fallback sequence
        fallbacks = [
            "Yes, please go ahead.",
            "That sounds right.",
            "Thank you.",
            "###STOP###",
        ]
        resp = fallbacks[min(self._fallback_idx, len(fallbacks) - 1)]
        self._fallback_idx += 1
        return resp

    def _extract_opening(self, instruction: str) -> str:
        # Try to extract the first sentence as the opening request
        sentences = instruction.split(".")
        if sentences:
            return sentences[0].strip() + "."
        return instruction[:200]
