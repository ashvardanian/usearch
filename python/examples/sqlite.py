# !pip install numpy requests pillow usearch uform

import sqlite3
import random
from io import BytesIO

import numpy as np
import requests
import usearch
import uform
from PIL import Image

# Existing code
num_entries = 1000
model = uform.load("unum-cloud/uform-vl-english")

coordinates_ny = (40.7128, -74.0060)  # New York
coordinates_sf = (37.7749, -122.4194)  # San Francisco
coordinates_la = (34.0522, -118.2437)  # Los Angeles
coordinates_ldn = (51.5074, -0.1278)  # London
coordinates_tk = (35.6895, 139.6917)  # Tokyo
coordinates_all = [
    coordinates_ny,
    coordinates_sf,
    coordinates_la,
    coordinates_ldn,
    coordinates_tk,
]

image_urls = [
    "https://images.pexels.com/photos/8561771/pexels-photo-8561771.jpeg?cs=srgb&dl=pexels-abdulwahab-alawadhi-8561771.jpg&fm=jpg",
    "https://techcrunch.com/wp-content/uploads/2013/02/india_bangalore_bus_.jpg",
    "https://www.motortrend.com/uploads/2022/03/Fiat-500-EV-first-drive-1.jpg?fit=around%7C875:492",
    "https://images.pexels.com/photos/9331953/pexels-photo-9331953.jpeg?auto=compress&cs=tinysrgb&w=1260&h=750&dpr=1",
    "https://i.ytimg.com/vi/0SZ6K3BQAAg/maxresdefault.jpg",
    "https://images.unsplash.com/photo-1596812471595-c37b27114e1e?ixlib=rb-4.0.3&ixid=M3wxMjA3fDB8MHxzZWFyY2h8Mnx8YXBlcnRhfGVufDB8fDB8fHww&w=1000&q=80",
    "https://cdn.jdpower.com/JDP_2023%20Alfa%20Romeo%20Tonale%20Veloce%20Blue%20Front%20Quarter%20View%20European%20spec.jpg",
]

# Download the images, load them into Pillow, and encode with UForm
image_features = [requests.get(url) for url in image_urls]
image_features = [Image.open(BytesIO(response.content)) for response in image_features]
image_features = model.preprocess_image(image_features)
image_features = model.encode_image(image_features)

conn = sqlite3.connect(":memory:")
conn.enable_load_extension(True)
conn.load_extension(usearch.sqlite)


# Create a table that contains: latitude, longitude, license_plate, image_url, image_embedding_f32.
# All of those are random generated, except for embeddings, which match the URL.
cursor = conn.cursor()
cursor.execute(
    f"""
    CREATE TABLE IF NOT EXISTS vector_table (
        id INTEGER PRIMARY KEY,
        latitude FLOAT,
        longitude FLOAT,
        license_plate TEXT,
        image_url TEXT,
        image_embedding_f32 BLOB
    )
"""
)

# Generate and insert random entries
for i in range(num_entries):
    # Generate a random 256-dimensional vector
    image_idx: int = np.random.randint(0, len(image_urls) - 1)
    image_url: str = image_urls[image_idx]
    image_embedding: np.ndarray = image_features[image_idx]

    # The license plate will have "XXX0000" format
    license_plate = "".join(
        [random.choice("ABCDEFGHIJKLMNOPQRSTUVWXYZ") for i in range(3)]
        + [random.choice("0123456789") for i in range(4)]
    )

    # Pick any city
    lat, lon = random.choice(coordinates_all)
    lat += random.uniform(-0.01, 0.01)
    lon += random.uniform(-0.01, 0.01)

    # Insert the vector into the database as scalars
    cursor.execute(
        f"""
        INSERT INTO vector_table (latitude, longitude, license_plate, image_url, image_embedding_f32) VALUES (?, ?, ?, ?, ?)
    """,
        (
            [
                lat,
                lon,
                license_plate,
                image_url,
                image_features.tolist(),
            ]
        ),
    )

# Commit changes
conn.commit()


# We then will filter points:
#   - within specific `distance_haversine_meters` radius from New York,
#   - with at most 2 mistakes in the recognized `license_plate`,
#   - sorted by the semantic similarity to the query "red pickup".
text_embedding = model.encode_text(model.preprocess_text(["Red Pickup"]))


similarities = """
SELECT 
    a.id AS id1,
    b.id AS id2,
    distance_cosine_f32(a.image_embedding_f32, b.image_embedding_f32) AS cosine_f32,
    distance_haversine_meters(a.latitude, a.longitude, b.latitude, b.longitude) AS haversine_meters,
    distance_levenshtein(a.title, b.title) AS levenshtein
FROM 
    vector_table AS a,
    vector_table AS b
WHERE 
    a.id < b.id;
"""
cursor.execute(similarities)

for (
    a,
    b,
    cosine_f32,
    cosine_f16,
    haversine,
    levenshtein,
) in cursor.fetchall():
    # assert math.isclose(cosine_json, cosine_f32, abs_tol=0.1)
    # assert math.isclose(cosine_json, cosine_f16, abs_tol=0.1)
    print(a, b, cosine_f32, cosine_f16, haversine, levenshtein)
