-- Create parts table if it doesn't exist
CREATE TABLE IF NOT EXISTS parts (
    part_name TEXT,
    part_id VARCHAR(255),
    mpn_id VARCHAR(255),
    part_price DECIMAL(10, 2),
    install_difficulty VARCHAR(255),
    install_time VARCHAR(255),
    symptoms TEXT,
    appliance_types TEXT,
    replace_parts TEXT,
    brand VARCHAR(255),
    availability VARCHAR(255),
    install_video_url TEXT,
    product_url TEXT
);

-- Load data from CSV file (use absolute path)
LOAD DATA LOCAL INFILE '/Users/prakhardungarwal/Downloads/partselect-agent-main-final/data/all_parts.csv'
INTO TABLE parts
FIELDS TERMINATED BY ','
ENCLOSED BY '"'
ESCAPED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS
(part_name, part_id, mpn_id, part_price, install_difficulty, install_time, 
 symptoms, appliance_types, replace_parts, brand, availability, 
 install_video_url, product_url);

