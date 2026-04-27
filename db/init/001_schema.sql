CREATE TABLE IF NOT EXISTS products (
  sku TEXT PRIMARY KEY,
  name TEXT NOT NULL,
  category TEXT NOT NULL,
  price NUMERIC(10, 2) NOT NULL,
  inventory INTEGER NOT NULL DEFAULT 0,
  rating NUMERIC(2, 1) NOT NULL,
  tags TEXT[] NOT NULL DEFAULT '{}',
  description TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS chat_sessions (
  id TEXT PRIMARY KEY,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS orders (
  id TEXT PRIMARY KEY,
  session_id TEXT REFERENCES chat_sessions(id),
  status TEXT NOT NULL,
  total NUMERIC(10, 2) NOT NULL,
  payload JSONB NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

INSERT INTO products (sku, name, category, price, inventory, rating, tags, description) VALUES
('RUN-TRAIL-01', 'Northline Waterproof Trail Shoe', 'shoes', 139, 18, 4.7, ARRAY['trail','waterproof','running','rain'], 'Grippy trail shoe with sealed upper and rock plate.'),
('RUN-ROAD-02', 'AeroKnit Road Runner', 'shoes', 118, 31, 4.5, ARRAY['road','running','lightweight'], 'Breathable daily trainer for pavement miles.'),
('HIKE-BOOT-03', 'RidgeLock Hiking Boot', 'boots', 172, 12, 4.8, ARRAY['hiking','waterproof','ankle-support'], 'Supportive boot for wet and rocky hikes.'),
('PACK-DAY-04', 'Transit 22L Daypack', 'bags', 86, 24, 4.4, ARRAY['commute','travel','laptop'], 'Structured daypack with laptop sleeve and bottle pockets.'),
('JKT-RAIN-05', 'Cloudbreak Rain Shell', 'jackets', 128, 20, 4.6, ARRAY['rain','waterproof','lightweight'], 'Packable shell with taped seams and adjustable hood.'),
('SOCK-MER-06', 'Merino Trail Socks', 'socks', 22, 80, 4.9, ARRAY['trail','running','merino'], 'Cushioned socks that manage moisture on long runs.')
ON CONFLICT (sku) DO NOTHING;
