-- Schema for database of switches

create table system (
	id 	integer primary key autoincrement not null,
	name text
);

create table command (
	id 	integer primary key autoincrement not null,
	command	text not null,
	man_group integer,
	system_id integer references system(id) not null
);

create table switch (
	id integer primary key autoincrement not null,
	switch	text not null, 
	command_id integer references command(id) not null
);
