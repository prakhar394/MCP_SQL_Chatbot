-- Create repairs table if it doesn't exist
CREATE TABLE IF NOT EXISTS repairs (
    Product VARCHAR(255),
    symptom VARCHAR(255),
    description TEXT,
    percentage INT,
    parts TEXT,
    symptom_detail_url TEXT,
    difficulty VARCHAR(255),
    repair_video_url TEXT
);

-- Load data from CSV file (use absolute path)
LOAD DATA LOCAL INFILE '/Users/prakhardungarwal/Downloads/partselect-agent-main-final/data/all_repairs.csv'
INTO TABLE repairs
FIELDS TERMINATED BY ','
ENCLOSED BY '"'
ESCAPED BY '"'
LINES TERMINATED BY '\n'
IGNORE 1 ROWS
(Product, symptom, description, percentage, parts, symptom_detail_url, 
 difficulty, repair_video_url);

