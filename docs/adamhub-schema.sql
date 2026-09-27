-- ============================================================
-- AdamHUB Relational Database Schema (SQL DDL for Draw.io)
-- Import dans Draw.io : Arranger > Insérer > Avancé > SQL
-- ============================================================

-- 1. Utilisateurs & Contexte IA
CREATE TABLE "user" (
    id SERIAL PRIMARY KEY,
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,
    display_name VARCHAR(100) NOT NULL,
    api_key_hash VARCHAR(64) UNIQUE,
    ntfy_topic VARCHAR(100),
    is_active BOOLEAN DEFAULT TRUE,
    email_verified BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE TABLE "userprofile" (
    id SERIAL PRIMARY KEY,
    user_id INTEGER UNIQUE NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    dietary_preferences JSONB,
    fitness_goals VARCHAR(500),
    lifestyle_notes VARCHAR(1000),
    ai_tone VARCHAR(50) DEFAULT 'direct',
    onboarding_completed BOOLEAN DEFAULT FALSE
);

CREATE TABLE "usermemory" (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    category VARCHAR(50) NOT NULL,
    fact VARCHAR(1000) NOT NULL,
    confidence FLOAT DEFAULT 1.0,
    source VARCHAR(50) DEFAULT 'conversation',
    is_active BOOLEAN DEFAULT TRUE
);

-- 2. Recettes & Planification des Repas
CREATE TABLE "recipe" (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES "user"(id) ON DELETE SET NULL,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    instructions TEXT NOT NULL,
    steps JSONB,
    utensils JSONB,
    prep_minutes INTEGER DEFAULT 0,
    cook_minutes INTEGER DEFAULT 0,
    servings INTEGER DEFAULT 1,
    tags JSONB
);

CREATE TABLE "supermarketsearchcache" (
    id SERIAL PRIMARY KEY,
    store VARCHAR(50) NOT NULL,
    query VARCHAR(255) NOT NULL,
    external_id VARCHAR(100),
    name VARCHAR(255) NOT NULL,
    brand VARCHAR(100),
    price_amount FLOAT,
    image_url VARCHAR(500),
    expires_at TIMESTAMP WITH TIME ZONE NOT NULL
);

CREATE TABLE "recipeingredient" (
    id SERIAL PRIMARY KEY,
    recipe_id INTEGER NOT NULL REFERENCES "recipe"(id) ON DELETE CASCADE,
    cache_id INTEGER REFERENCES "supermarketsearchcache"(id) ON DELETE SET NULL,
    name VARCHAR(255) NOT NULL,
    quantity FLOAT DEFAULT 1,
    unit VARCHAR(50) DEFAULT 'item',
    store VARCHAR(50),
    external_id VARCHAR(100),
    price_text VARCHAR(50)
);

CREATE TABLE "mealplan" (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES "user"(id) ON DELETE CASCADE,
    recipe_id INTEGER NOT NULL REFERENCES "recipe"(id) ON DELETE CASCADE,
    planned_at TIMESTAMP WITH TIME ZONE NOT NULL,
    slot VARCHAR(50),
    servings_override INTEGER,
    auto_add_missing_ingredients BOOLEAN DEFAULT TRUE
);

CREATE TABLE "mealplancookconfirmation" (
    id SERIAL PRIMARY KEY,
    meal_plan_id INTEGER UNIQUE NOT NULL REFERENCES "mealplan"(id) ON DELETE CASCADE,
    confirmed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    pantry_consumption JSONB
);

-- 3. Courses, Garde-Manger & Synchronisation
CREATE TABLE "groceryitem" (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES "user"(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    quantity FLOAT DEFAULT 1,
    unit VARCHAR(50) DEFAULT 'item',
    category VARCHAR(100),
    checked BOOLEAN DEFAULT FALSE,
    in_cart BOOLEAN DEFAULT FALSE,
    priority INTEGER DEFAULT 3,
    external_id VARCHAR(100)
);

CREATE TABLE "pantryitem" (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES "user"(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    quantity FLOAT DEFAULT 0,
    unit VARCHAR(50) DEFAULT 'item',
    min_quantity FLOAT DEFAULT 0,
    expires_at DATE,
    location VARCHAR(100)
);

CREATE TABLE "grocerypantrysync" (
    id SERIAL PRIMARY KEY,
    grocery_item_id INTEGER NOT NULL REFERENCES "groceryitem"(id) ON DELETE CASCADE,
    pantry_item_id INTEGER NOT NULL REFERENCES "pantryitem"(id) ON DELETE CASCADE,
    added_quantity FLOAT DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- 4. Supermarché, Configuration & Drive Automatisé
CREATE TABLE "userstorepreference" (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    store VARCHAR(50) NOT NULL,
    external_store_id VARCHAR(100) NOT NULL,
    store_label VARCHAR(255) NOT NULL,
    pickup_type VARCHAR(32) DEFAULT 'quai',
    optimization_strategy VARCHAR(32) DEFAULT 'mdd',
    CONSTRAINT uq_user_store UNIQUE (user_id, store)
);

CREATE TABLE "supermarketconnection" (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES "user"(id) ON DELETE CASCADE,
    store VARCHAR(50) NOT NULL,
    label VARCHAR(100) NOT NULL,
    cookies_encrypted TEXT NOT NULL,
    is_active BOOLEAN DEFAULT FALSE,
    customer_uuid VARCHAR(100)
);

CREATE TABLE "supermarketcart" (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES "user"(id) ON DELETE CASCADE,
    store VARCHAR(50) NOT NULL,
    status VARCHAR(32) DEFAULT 'draft',
    validated_at TIMESTAMP WITH TIME ZONE,
    CONSTRAINT uq_supermarketcart_user_store UNIQUE (user_id, store)
);

CREATE TABLE "supermarketcartitem" (
    id SERIAL PRIMARY KEY,
    cart_id INTEGER NOT NULL REFERENCES "supermarketcart"(id) ON DELETE CASCADE,
    cache_id INTEGER REFERENCES "supermarketsearchcache"(id) ON DELETE SET NULL,
    external_id VARCHAR(100),
    name VARCHAR(255) NOT NULL,
    price_amount FLOAT,
    quantity INTEGER DEFAULT 1
);

CREATE TABLE "grocerytocartjob" (
    id SERIAL PRIMARY KEY,
    user_id INTEGER NOT NULL REFERENCES "user"(id) ON DELETE CASCADE,
    store VARCHAR(50) NOT NULL,
    external_store_id VARCHAR(100) NOT NULL,
    status VARCHAR(32) DEFAULT 'draft',
    optimization_strategy VARCHAR(32) DEFAULT 'mdd',
    items_count INTEGER DEFAULT 0,
    matched_count INTEGER DEFAULT 0,
    estimated_total_cents INTEGER DEFAULT 0
);

CREATE TABLE "matchedcartitem" (
    id SERIAL PRIMARY KEY,
    job_id INTEGER NOT NULL REFERENCES "grocerytocartjob"(id) ON DELETE CASCADE,
    grocery_item_id INTEGER REFERENCES "groceryitem"(id) ON DELETE SET NULL,
    cache_id INTEGER REFERENCES "supermarketsearchcache"(id) ON DELETE SET NULL,
    name VARCHAR(255) NOT NULL,
    quantity FLOAT DEFAULT 1.0,
    unit_price_cents INTEGER DEFAULT 0,
    total_price_cents INTEGER DEFAULT 0,
    match_type VARCHAR(32) DEFAULT 'mdd',
    status VARCHAR(32) DEFAULT 'staged'
);

CREATE TABLE "substituteproposal" (
    id SERIAL PRIMARY KEY,
    matched_item_id INTEGER NOT NULL REFERENCES "matchedcartitem"(id) ON DELETE CASCADE,
    alternative_cache_id INTEGER NOT NULL REFERENCES "supermarketsearchcache"(id) ON DELETE CASCADE,
    alternative_name VARCHAR(255) NOT NULL,
    price_difference_cents INTEGER DEFAULT 0,
    reason VARCHAR(255) NOT NULL,
    status VARCHAR(32) DEFAULT 'pending'
);

-- 5. Organisation, Tâches, Habitudes & Notes
CREATE TABLE "task" (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES "user"(id) ON DELETE SET NULL,
    title VARCHAR(255) NOT NULL,
    description TEXT,
    subtasks JSONB,
    status VARCHAR(32) DEFAULT 'todo',
    priority VARCHAR(32) DEFAULT 'medium',
    due_at TIMESTAMP WITH TIME ZONE
);

CREATE TABLE "habit" (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES "user"(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    frequency VARCHAR(32) DEFAULT 'daily',
    streak INTEGER DEFAULT 0,
    active BOOLEAN DEFAULT TRUE
);

CREATE TABLE "habitlog" (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES "user"(id) ON DELETE CASCADE,
    habit_id INTEGER NOT NULL REFERENCES "habit"(id) ON DELETE CASCADE,
    logged_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    value INTEGER DEFAULT 1
);

CREATE TABLE "goal" (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES "user"(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    status VARCHAR(32) DEFAULT 'planned',
    progress_percent INTEGER DEFAULT 0,
    target_date DATE
);

CREATE TABLE "goalmilestone" (
    id SERIAL PRIMARY KEY,
    goal_id INTEGER NOT NULL REFERENCES "goal"(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    due_at TIMESTAMP WITH TIME ZONE,
    completed BOOLEAN DEFAULT FALSE
);

CREATE TABLE "note" (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES "user"(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    content TEXT NOT NULL,
    kind VARCHAR(32) DEFAULT 'note',
    pinned BOOLEAN DEFAULT FALSE
);

-- 6. Sport & Santé
CREATE TABLE "fitnesssession" (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES "user"(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    session_type VARCHAR(32) DEFAULT 'mixed',
    planned_at TIMESTAMP WITH TIME ZONE NOT NULL,
    duration_minutes INTEGER DEFAULT 45,
    exercises JSONB,
    status VARCHAR(32) DEFAULT 'planned',
    effort_rating INTEGER,
    calories_burned FLOAT
);

CREATE TABLE "fitnessmeasurement" (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES "user"(id) ON DELETE CASCADE,
    recorded_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    body_weight_kg FLOAT,
    body_fat_pct FLOAT,
    resting_hr INTEGER,
    sleep_hours FLOAT,
    steps INTEGER
);

-- 7. Finances & Abonnements
CREATE TABLE "account" (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES "user"(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    account_type VARCHAR(32) DEFAULT 'savings',
    balance FLOAT DEFAULT 0.0,
    currency VARCHAR(8) DEFAULT 'EUR',
    is_active BOOLEAN DEFAULT TRUE
);

CREATE TABLE "savingsgoal" (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES "user"(id) ON DELETE CASCADE,
    account_id INTEGER REFERENCES "account"(id) ON DELETE SET NULL,
    title VARCHAR(255) NOT NULL,
    target_amount FLOAT NOT NULL,
    current_amount FLOAT DEFAULT 0.0,
    completed BOOLEAN DEFAULT FALSE
);

CREATE TABLE "financetransaction" (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES "user"(id) ON DELETE CASCADE,
    kind VARCHAR(32) NOT NULL,
    amount FLOAT NOT NULL,
    category VARCHAR(100) NOT NULL,
    occurred_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    is_recurring BOOLEAN DEFAULT FALSE
);

CREATE TABLE "budget" (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES "user"(id) ON DELETE CASCADE,
    month VARCHAR(7) NOT NULL,
    category VARCHAR(100) NOT NULL,
    monthly_limit FLOAT NOT NULL,
    alert_threshold FLOAT DEFAULT 0.8
);

CREATE TABLE "subscription" (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES "user"(id) ON DELETE CASCADE,
    name VARCHAR(255) NOT NULL,
    amount FLOAT NOT NULL,
    interval VARCHAR(32) DEFAULT 'monthly',
    next_due_date DATE NOT NULL,
    active BOOLEAN DEFAULT TRUE
);

-- 8. Calendrier & Hub
CREATE TABLE "calendaritem" (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES "user"(id) ON DELETE SET NULL,
    title VARCHAR(255) NOT NULL,
    start_at TIMESTAMP WITH TIME ZONE NOT NULL,
    end_at TIMESTAMP WITH TIME ZONE NOT NULL,
    category VARCHAR(32) DEFAULT 'general',
    source VARCHAR(32) DEFAULT 'manual',
    source_ref_id INTEGER,
    completed BOOLEAN DEFAULT FALSE
);

CREATE TABLE "calendarevent" (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES "user"(id) ON DELETE CASCADE,
    title VARCHAR(255) NOT NULL,
    start_at TIMESTAMP WITH TIME ZONE NOT NULL,
    end_at TIMESTAMP WITH TIME ZONE NOT NULL,
    location VARCHAR(255),
    type VARCHAR(32) DEFAULT 'personal',
    all_day BOOLEAN DEFAULT FALSE
);

CREATE TABLE "calendarfeed" (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES "user"(id) ON DELETE CASCADE,
    token VARCHAR(255) UNIQUE NOT NULL,
    name VARCHAR(100) NOT NULL,
    sources JSONB,
    active BOOLEAN DEFAULT TRUE
);
