"""Versioned candidate taxonomy for conditional CLIP classification.

These candidates are evaluated only after RAM++ or YOLO detects the parent
concept. Country inference is intentionally limited to explicit national flags;
ordinary scenery, people, clothing, and text never trigger it.
"""

FINE_GRAINED_LABELS: dict[str, list[str]] = {
    "animal": [
        "dog", "cat", "horse", "cow", "sheep", "goat", "rabbit", "deer",
        "elephant", "giraffe", "zebra", "lion", "tiger", "bear", "wolf",
        "fox", "monkey", "kangaroo",
    ],
    "dog": [
        "Labrador Retriever", "German Shepherd", "Golden Retriever", "French Bulldog",
        "English Bulldog", "Poodle", "Beagle", "Rottweiler", "Dachshund",
        "Siberian Husky", "Alaskan Malamute", "Chihuahua", "Shih Tzu", "Boxer",
        "Great Dane", "Pomeranian", "Border Collie", "Doberman Pinscher",
        "Pembroke Welsh Corgi", "Australian Shepherd", "Cocker Spaniel", "Pug",
        "Samoyed", "Saint Bernard", "Belgian Malinois", "Akita", "Dalmatian",
        "Indian Pariah Dog", "mixed-breed dog",
    ],
    "cat": [
        "Siamese cat", "Persian cat", "Maine Coon", "Bengal cat", "Sphynx cat",
        "British Shorthair", "Ragdoll cat", "Scottish Fold", "Russian Blue",
        "Abyssinian cat", "Norwegian Forest cat", "American Shorthair",
        "domestic shorthair cat", "domestic longhair cat", "mixed-breed cat",
    ],
    "bird": [
        "sparrow", "eagle", "parrot", "owl", "peacock", "pigeon", "duck",
        "crow", "flamingo", "swan", "goose", "kingfisher", "woodpecker",
        "hummingbird", "seagull", "penguin", "ostrich", "falcon", "robin",
        "macaw", "cockatoo", "chicken", "turkey",
    ],
    "horse": [
        "Arabian horse", "Thoroughbred horse", "American Quarter Horse",
        "Appaloosa horse", "Friesian horse", "Mustang horse", "Clydesdale horse",
        "Shetland pony", "Icelandic horse", "Paint Horse", "mixed-breed horse",
    ],
    "fish": [
        "goldfish", "koi fish", "betta fish", "clownfish", "angelfish", "tuna",
        "salmon", "trout", "carp", "catfish", "shark", "ray", "seahorse",
        "pufferfish", "sardine", "mackerel",
    ],
    "flower": [
        "rose", "tulip", "sunflower", "daisy", "orchid", "lily", "lotus",
        "marigold", "hibiscus", "jasmine", "lavender", "chrysanthemum",
        "daffodil", "dahlia", "peony", "poppy", "carnation", "bougainvillea",
    ],
    "tree": [
        "oak tree", "maple tree", "pine tree", "palm tree", "coconut tree",
        "mango tree", "banyan tree", "birch tree", "willow tree", "cedar tree",
        "redwood tree", "cherry blossom tree", "eucalyptus tree", "baobab tree",
    ],
    "fruit": [
        "apple", "banana", "orange", "mango", "grape", "watermelon", "pineapple",
        "strawberry", "blueberry", "papaya", "guava", "pomegranate", "peach",
        "pear", "kiwi", "dragon fruit", "coconut", "lemon", "avocado",
    ],
    "car": [
        "sedan", "SUV", "pickup truck", "hatchback", "sports car", "convertible",
        "station wagon", "minivan", "luxury car", "electric car", "rally car",
        "race car", "classic car", "off-road vehicle",
    ],
    "motorcycle": [
        "sport motorcycle", "cruiser motorcycle", "touring motorcycle", "scooter",
        "dirt bike", "adventure motorcycle", "cafe racer", "moped",
        "electric motorcycle",
    ],
    "bicycle": [
        "road bicycle", "mountain bicycle", "hybrid bicycle", "BMX bicycle",
        "cruiser bicycle", "folding bicycle", "electric bicycle", "cargo bicycle",
    ],
    "airplane": [
        "passenger jet", "private jet", "cargo airplane", "propeller airplane",
        "fighter jet", "seaplane", "glider", "biplane", "commercial airliner",
    ],
    "boat": [
        "sailboat", "motorboat", "fishing boat", "yacht", "cargo ship",
        "container ship", "cruise ship", "canoe", "kayak", "ferry", "speedboat",
        "submarine",
    ],
    "flag": [
        "India", "United States", "United Kingdom", "Canada", "Australia", "Japan",
        "China", "South Korea", "Germany", "France", "Italy", "Spain", "Portugal",
        "Brazil", "Argentina", "Mexico", "South Africa", "Nigeria", "Kenya", "Egypt",
        "Saudi Arabia", "United Arab Emirates", "Israel", "Turkey", "Russia", "Ukraine",
        "Pakistan", "Bangladesh", "Sri Lanka", "Nepal", "Bhutan", "Indonesia",
        "Singapore", "Malaysia", "Thailand", "Vietnam", "Philippines", "New Zealand",
        "Switzerland", "Sweden", "Norway", "Denmark", "Finland", "Netherlands",
        "Belgium", "Ireland", "Greece",
    ],
}

FINE_GRAINED_TRIGGER_ALIASES = {
    "puppy": "dog", "kitten": "cat", "automobile": "car", "motorbike": "motorcycle",
    "bike": "bicycle", "cycle": "bicycle", "aircraft": "airplane", "plane": "airplane",
    "ship": "boat", "national flag": "flag",
}

FINE_GRAINED_PROMPT_TEMPLATES = {
    "animal": "a photo of a {label}",
    "dog": "a photo of a {label} dog",
    "cat": "a photo of a {label}",
    "bird": "a photo of a {label} bird",
    "horse": "a photo of a {label}",
    "fish": "a photo of a {label}",
    "flower": "a photo of a {label} flower",
    "tree": "a photo of a {label}",
    "fruit": "a photo of a {label} fruit",
    "car": "a photo of a {label}",
    "motorcycle": "a photo of a {label}",
    "bicycle": "a photo of a {label}",
    "airplane": "a photo of a {label}",
    "boat": "a photo of a {label}",
    "flag": "the national flag of {label}",
}

FINE_GRAINED_CONFIDENCE_THRESHOLDS = {"flag": 0.65, "animal": 0.55}
FINE_GRAINED_MINIMUM_MARGINS = {"flag": 0.12, "animal": 0.10}
DEFAULT_FINE_GRAINED_CONFIDENCE_THRESHOLD = 0.60
DEFAULT_FINE_GRAINED_MINIMUM_MARGIN = 0.08
