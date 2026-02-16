CREATE DATABASE IF NOT EXISTS travel_world;
USE travel_world;

CREATE TABLE users (
    id INT AUTO_INCREMENT PRIMARY KEY,
    first_name VARCHAR(100),
    last_name VARCHAR(100),
    contact VARCHAR(20),
    email VARCHAR(150) UNIQUE,
    password VARCHAR(255),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE national_states (
    id INT AUTO_INCREMENT PRIMARY KEY,
    state_name VARCHAR(100),
    state_description TEXT,
    state_image VARCHAR(255),
    places_count INT DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE places (
    id INT AUTO_INCREMENT PRIMARY KEY,
    state_id INT,
    place_name VARCHAR(150),
    district VARCHAR(100),
    description TEXT,
    image VARCHAR(255),
    location_link TEXT,
    type VARCHAR(255),
    best_time_from DATE,
    best_time_to DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (state_id) REFERENCES national_states(id) ON DELETE CASCADE
);


CREATE TABLE completed (
    id INT AUTO_INCREMENT PRIMARY KEY,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
