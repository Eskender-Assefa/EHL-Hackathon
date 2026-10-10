"""Lookup from BMW's own `Vfc level2 Name` topics to the project's C01-C10 taxonomy.

The workbooks already classify each feedback row by topic. Mapping those 225 labels once is more
reliable than re-deriving a category from words in the comment. The assignment is a project
judgement, not an official BMW standard: review the table before quoting category totals.
"""
from __future__ import annotations

import re

_TOPICS_BY_CATEGORY = {
    "C01": (
        "Drivetrain", "Drive, driving dynamics and chassis, overall technology", "Handling / Riding",
        "Transmission", "Steering", "Launch Control", "Engine acoustics / engine sound", "Exhaust system",
        "Operate selector lever", "Shift paddle", "My Modes / driving experience", "Starting engine",
        "Start engine/switch on drive readiness", "Pedals, operate", "ground clearance",
    ),
    "C02": (
        "Electric Range", "Charge high-voltage battery", "Charging cable", "High voltage battery",
        "High voltage battery, preconditioning", "High-voltage charging power socket",
        "Public charging / external providers", "Wallbox, charging / home charging",
        "Route optimized for charging", "Bidirectional charging", "Brake Energy Regeneration / recuperation",
        "Opening/closing charging socket cover", "Fuel tank", "Automatic engine start-stop function (MSA)",
        "Vehicle battery",
    ),
    "C03": ("BMW ConnectedDrive upgrades/ MINI CONNECTED upgrades",),
    "C04": (
        "Airbags", "Blind spot monitoring", "Braking", "Cross Traffic Warning Rear with Brake Intervention",
        "Emergency Stop Assistant", "Emergency request", "Fatigue Alert", "Front collision warning",
        "Impression of safety", "Intersection Warning with Brake Intervention", "Lane departure warning",
        "Night Vision", "Rear-end collision warning", "Seat belts", "Child restraint seat",
        "Child restraint seat, use", "Child safety latch", "Vehicle safety, overall technology",
        "Dynamic Stability Control", "Dynamic Stability Control (DSC)", "Parking brake", "Automatic-hold",
        "Tire pressure control", "Traffic Light And Sign Warning", "Anti-theft alarm system", "Horns",
    ),
    "C05": (
        "Seats", "Seat massage", "Seat memory", "Seating, ventilate / heat", "Adjustment of lower lumbar support",
        "Headrest, adjust", "Headrests, rear", "Heated steering wheel", "Air conditioning control panel",
        "Air conditioning, overall technology", "Air conditioning, setting", "Blower function",
        "Vehicle, climatization", "Cooling", "Auxiliary heater function", "Panel heating", "Interior acoustics",
        "Interior comfort", "Cushioning / damping vehicle", "Self-leveling suspension", "Vehicle, access and exit",
        "Sun protection", "Sun visor, front", "Heated rear window", "Center armrest, front",
        "Space / spatial impression", "RSC tire",
    ),
    "C06": (
        "Exterior", "Exterior design", "Exterior lighting", "Exterior rearview mirror", "Fog light",
        "High-beam assistant", "Flashing", "Bumper, front", "Bumper, rear", "Hood", "Hood, open / close",
        "Radiator grille", "Roof", "Panorama glass roof", "Running board", "Side sill trim panel",
        "Wheels / tires", "Windshield", "Windshield wiper", "Rear wiper", "Wash / wipe switch",
        "Rain sensor mode", "Outer door handle, front", "Outer door handle, rear", "Door, front",
        "Door, open / close", "Automatic doors", "Trunk lid", "Trunk lid, open / close",
        "non-contact trunk lid opening", "Fuel filler flap , open / close", "Welcome Light Carpet",
        "Opening / closing convertible top / hardtop", "Side window, open / close",
    ),
    "C07": (
        "Android Auto", "Apple CarPlay", "Apps (in-car)", "Apps (smartphone)", "Audio mode, sound",
        "BMW Online / MINI Online", "CD / DVD changer, playback",
        "ConnectedDrive and Infotainment, overall technology",
        "ConnectedDrive services (smartphone) technology overall", "Controller operation",
        "Customer Account (My BMW / MINI Portal)", "Digital Key", "Display, time", "Drive Recorder",
        "Driver profile", "Driver's Guide App", "Gesture control", "Head-Up Display", "Instrument cluster",
        "Intelligent Personal Assistant", "Intelligent Personal Assistant, activation word",
        "Manage / pair mobile device (Bluetooth)", "Map update", "My BMW / MINI Portal",
        "My BMW App / MINI App", "Navigation", "Operating concept, operating system", "Personal eSIM",
        "Priorities for telephones", "Radio function", "Real Time Traffic Information (RTTI)",
        "Rear seat entertainment", "Remote 3D View (My BMW App / MINI App)",
        "Remote Engine Start (My BMW App / MINI App)",
        "Remote Services & Remote Keyless Entry (My BMW App/MINI App)", "Remote Software Upgrade/RSU",
        "Remote interior camera (My BMW App / MINI App)", "Screen mirroring", "Smart POI search",
        "Teleservices", "Touch Command", "Touch screen, operation", "Traffic Camera Information",
        "Video: playback / streaming", "Voice control / speech recognition", "Wi-Fi connection",
        "WiFi hotspot", "Multi-function steering wheel operation", "Interior camera", "Caring Car",
        "Experience Modes", "Resting state after door opening",
    ),
    "C08": (
        "Ambient light", "Center console, front", "Cupholder", "Door, finisher panel, front", "Floor mat",
        "Glove box", "Grab handle", "Instrument panel", "Interior", "Interior design",
        "Interior rearview mirror", "Luggage compartment", "Steering wheel", "Storage compartments",
        "Upholstery / interior trim", "Vehicle interior, lighting", "Trunk light", "Through-loading facility",
        "Frunk", "Mobile device, wireless charging", "USB port", "12 V connection",
        "Light switch operating unit", "Roof function centre",
    ),
    "C09": (
        "(Active) cruise control", "Back-up Assistant", "Driver assistance, automated driving, overall technology",
        "Highway assistant", "Lane Change Assistant", "Park Distance Control (PDC)", "Parking Assistant",
        "Remote controlled parking", "Steering and lane guide assist", "Traffic Jam Assistant",
        "All-round view", "Surround View", "Side View", "Rear view camera", "Speed Limit Assistant",
    ),
    "C10": (
        "Accessories / Parts", "General enquiry: customer feedback", "Owner's Manual", "Engine oil",
        "Washer fluid, top up", "Tirefit", "Trailer, use", "Towing eye", "Garage door opener",
        "Interior mirror, garage door opener", "Comfort Access", "Vehicle key", "Display key",
        "Vehicle, lock / unlock", "Remote Engine Start (Vehicle Key )", "Body equipment, overall technology",
    ),
}

# BMW uses these two labels for overall impressions, so a count under them is not one feature.
GENERIC_TOPICS = frozenset({"Body equipment, overall technology", "General enquiry: customer feedback"})


def _normalise(topic: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", topic.casefold()).strip()


BMW_TOPIC_CATEGORY = {
    _normalise(topic): category for category, topics in _TOPICS_BY_CATEGORY.items() for topic in topics
}


def topic_category(topic: str) -> str | None:
    """Return the C01-C10 category of a BMW level-2 topic, or None if the topic is not in the table."""
    return BMW_TOPIC_CATEGORY.get(_normalise(topic))
