create table feeds (
  id integer primary key autoincrement,
  uri text not null
);

-- currently not used; intended for future search feature
create table episodes (
  id integer primary key autoincrement,
  title text not null,
  description text not null,
  stream_uri text not null,
  duration text not null
);

create table radios (
  id integer primary key autoincrement,
  name text not null,
  url text not null,
  stream_uri text not null
);
