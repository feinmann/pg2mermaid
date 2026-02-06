--
-- Simple PostgreSQL database for testing
--

CREATE TABLE users (
    id serial PRIMARY KEY,
    email varchar(255) NOT NULL UNIQUE,
    name text,
    created_at timestamp DEFAULT now()
);

CREATE TABLE posts (
    id serial PRIMARY KEY,
    user_id integer NOT NULL,
    title text NOT NULL,
    body text,
    published boolean DEFAULT false,
    created_at timestamp DEFAULT now()
);

CREATE TABLE comments (
    id serial PRIMARY KEY,
    post_id integer NOT NULL,
    user_id integer NOT NULL,
    content text NOT NULL,
    created_at timestamp DEFAULT now()
);

CREATE TABLE tags (
    id serial PRIMARY KEY,
    name varchar(50) NOT NULL UNIQUE
);

CREATE TABLE post_tags (
    post_id integer NOT NULL,
    tag_id integer NOT NULL,
    PRIMARY KEY (post_id, tag_id)
);

-- Foreign key constraints
ALTER TABLE posts
    ADD CONSTRAINT posts_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

ALTER TABLE comments
    ADD CONSTRAINT comments_post_id_fkey FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE;

ALTER TABLE comments
    ADD CONSTRAINT comments_user_id_fkey FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE;

ALTER TABLE post_tags
    ADD CONSTRAINT post_tags_post_id_fkey FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE;

ALTER TABLE post_tags
    ADD CONSTRAINT post_tags_tag_id_fkey FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE;
