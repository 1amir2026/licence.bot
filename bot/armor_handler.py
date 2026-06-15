# ====================== CONSTANTS ======================

ARMOR_TYPES = ["wooden", "stone", "iron", "chainmail", "golden", "diamond", "netherite"]

# نگاشت نام آرمور به نام فایل (بدون .png)
ARMOR_FILE_MAP = {
    "wooden":    "wooden",
    "stone":     "stone",
    "iron":      "iron",
    "chainmail": "chainmail",
    "golden":    "gold",
    "diamond":   "diamond",
    "netherite": "netherite",
}

# تمام تریم‌های ماینکرافت Java به ترتیب الفبا (none اول)
ARMOR_TRIMS = [
    "none",
    "coast",
    "dune",
    "eye",
    "host",
    "raiser",
    "rib",
    "sentry",
    "shaper",
    "silence",
    "snout",
    "spire",
    "tide",
    "vex",
    "ward",
    "wayfinder",
    "wild",
]

TRIM_SLOTS = ["helmet", "chestplate", "leggings", "boots"]
TRIM_SLOT_EMOJI = {
    "helmet":     "⛑",
    "chestplate": "🥋",
    "leggings":   "👖",
    "boots":      "👟",
}

BASE_DIR = Path(__file__).resolve().parent
ARMORS_DIR = BASE_DIR / "armors"

# state: user_id -> {"armor": str, "trims": {slot: int}}
armor_build_state: dict[int, dict] = {}

