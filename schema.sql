create table if not exists feeds (
  id integer primary key autoincrement,
  uri text not null,
  lastmodified text
);


-- currently not used; intended for future search feature
-- create table episodes (
--   id integer primary key autoincrement,
--   title text not null,
--   description text not null,
--   stream_uri text not null,
--   duration text not null
-- );

create table if not exists episodes (
  id integer primary key autoincrement,
  url text unique not null,
  position integer
);

create virtual table episode_search using fts4 (
  id,
  description,
  content
);


create table if not exists radios (
  id integer primary key autoincrement,
  name text not null,
  url text not null,
  stream_protocol text not null,
  stream_host text not null,
  stream_port integer not null,
  stream_url text not null
);
