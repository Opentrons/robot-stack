from typing import Dict, Final

# ------------------------------------------------------------------------------
# Alpha Channel
# ------------------------------------------------------------------------------

ALPHA_APP_WINDOWS_URL: Final[str] = "https://builds.opentrons.com/app/alpha.yml"
ALPHA_APP_MAC_URL: Final[str] = "https://builds.opentrons.com/app/alpha-mac.yml"
ALPHA_APP_LINUX_URL: Final[str] = "https://builds.opentrons.com/app/alpha-linux.yml"

# ------------------------------------------------------------------------------
# Beta Channel
# ------------------------------------------------------------------------------

BETA_APP_WINDOWS_URL: Final[str] = "https://builds.opentrons.com/app/beta.yml"
BETA_APP_MAC_URL: Final[str] = "https://builds.opentrons.com/app/beta-mac.yml"
BETA_APP_LINUX_URL: Final[str] = "https://builds.opentrons.com/app/beta-linux.yml"

# ------------------------------------------------------------------------------
# Latest Stable Channel
# ------------------------------------------------------------------------------

LATEST_APP_WINDOWS_URL: Final[str] = "https://builds.opentrons.com/app/latest.yml"
LATEST_APP_MAC_URL: Final[str] = "https://builds.opentrons.com/app/latest-mac.yml"
LATEST_APP_LINUX_URL: Final[str] = "https://builds.opentrons.com/app/latest-linux.yml"

# ------------------------------------------------------------------------------
# Internal Alpha Channel
# ------------------------------------------------------------------------------

INTERNAL_ALPHA_APP_WINDOWS_URL: Final[str] = "https://ot3-development.builds.opentrons.com/app/alpha.yml"
INTERNAL_ALPHA_APP_MAC_URL:     Final[str] = "https://ot3-development.builds.opentrons.com/app/alpha-mac.yml"
INTERNAL_ALPHA_APP_LINUX_URL:   Final[str] = "https://ot3-development.builds.opentrons.com/app/alpha-linux.yml"

# ------------------------------------------------------------------------------
# Internal Beta Channel
# ------------------------------------------------------------------------------

INTERNAL_BETA_APP_WINDOWS_URL: Final[str] = "https://ot3-development.builds.opentrons.com/app/beta.yml"
INTERNAL_BETA_APP_MAC_URL:     Final[str] = "https://ot3-development.builds.opentrons.com/app/beta-mac.yml"
INTERNAL_BETA_APP_LINUX_URL:   Final[str] = "https://ot3-development.builds.opentrons.com/app/beta-linux.yml"

# ------------------------------------------------------------------------------
# Internal Latest Stable Channel
# ------------------------------------------------------------------------------

INTERNAL_LATEST_APP_WINDOWS_URL: Final[str] = "https://ot3-development.builds.opentrons.com/app/latest.yml"
INTERNAL_LATEST_APP_MAC_URL:     Final[str] = "https://ot3-development.builds.opentrons.com/app/latest-mac.yml"
INTERNAL_LATEST_APP_LINUX_URL:   Final[str] = "https://ot3-development.builds.opentrons.com/app/latest-linux.yml"


# ------------------------------------------------------------------------------
# Informational ONLY for the App, Electron update uses the yml files
RELEASE_APP_JSON_URL: Final[str] = "https://builds.opentrons.com/app/releases.json"
RELEASE_APP_JSON_BUCKET: Final[str] = "builds.opentrons.com"
INTERNAL_RELEASE_APP_JSON_URL: Final[str] = "https://ot3-development.builds.opentrons.com/app/releases.json"
INTERNAL_RELEASE_APP_JSON_BUCKET: Final[str] = "ot3-development.builds.opentrons.com"


# ------------------------------------------------------------------------------
# Release JSON Metadata for the Flex and OT2
# ------------------------------------------------------------------------------

RELEASE_FLEX_JSON_URL: Final[str] = "https://builds.opentrons.com/ot3-oe/releases.json"
RELEASE_OT2_JSON_URL: Final[str] = "https://builds.opentrons.com/ot2-br/releases.json"

# ------------------------------------------------------------------------------
# Internal Release JSON Metadata for the Flex and OT2
# ------------------------------------------------------------------------------

# Informational ONLY for the App, Electron update uses the yml files

INTERNAL_RELEASE_FLEX_JSON_URL: Final[str] = "https://ot3-development.builds.opentrons.com/ot3-oe/releases.json"
INTERNAL_RELEASE_OT2_JSON_URL: Final[str] = "https://ot3-development.builds.opentrons.com/ot2-br/releases.json"

# ------------------------------------------------------------------------------
# URL maps
# ------------------------------------------------------------------------------

APP_YAML_URLS: Final[Dict[str, str]] = {
    "Alpha (Windows)": ALPHA_APP_WINDOWS_URL,
    "Alpha (Mac)": ALPHA_APP_MAC_URL,
    "Alpha (Linux)": ALPHA_APP_LINUX_URL,
    "Beta (Windows)": BETA_APP_WINDOWS_URL,
    "Beta (Mac)": BETA_APP_MAC_URL,
    "Beta (Linux)": BETA_APP_LINUX_URL,
    "Latest (Windows)": LATEST_APP_WINDOWS_URL,
    "Latest (Mac)": LATEST_APP_MAC_URL,
    "Latest (Linux)": LATEST_APP_LINUX_URL,
}

INTERNAL_APP_YAML_URLS: Final[Dict[str, str]] = {
    "Internal Alpha (Windows)": INTERNAL_ALPHA_APP_WINDOWS_URL,
    "Internal Alpha (Mac)": INTERNAL_ALPHA_APP_MAC_URL,
    "Internal Alpha (Linux)": INTERNAL_ALPHA_APP_LINUX_URL,
    "Internal Beta (Windows)": INTERNAL_BETA_APP_WINDOWS_URL,
    "Internal Beta (Mac)": INTERNAL_BETA_APP_MAC_URL,
    "Internal Beta (Linux)": INTERNAL_BETA_APP_LINUX_URL,
    "Internal Latest (Windows)": INTERNAL_LATEST_APP_WINDOWS_URL,
    "Internal Latest (Mac)": INTERNAL_LATEST_APP_MAC_URL,
    "Internal Latest (Linux)": INTERNAL_LATEST_APP_LINUX_URL,
}

ROBOT_JSON_URLS: Final[Dict[str, str]] = {
    "Flex": RELEASE_FLEX_JSON_URL,
    "OT2": RELEASE_OT2_JSON_URL,
}

INTERNAL_ROBOT_JSON_URLS: Final[Dict[str, str]] = {
    "Internal Flex": INTERNAL_RELEASE_FLEX_JSON_URL,
    "Internal OT2": INTERNAL_RELEASE_OT2_JSON_URL,
}
