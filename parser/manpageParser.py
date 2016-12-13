#!/usr/bin/env python
# coding: utf-8

# The MIT License (MIT)

# Copyright (c) 2015 Pavel Vomacka

# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:

# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.

# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import os
import sys
import re
import subprocess
import sqlite3
from shlex import split


# Configutation -- EDIT HERE:
os_namex = "fedora"
os_version = "24"
os_name = "fedora24" # FIXME
manpage_groups = ("1", "8",)


# Name of output file.
file_name = "./parsed_manpages.txt"
# Database path
db_path = "/tmp/switchTest/"
db_file = "switch.sqlite3"

# Database schema
schema_file = "./schema.sql"
opened_db = None


"""
    Prepare empty database.
"""
def create_empty_db():

    global opened_db

    if not os.path.exists(db_path):
        os.makedirs(db_path)

    with sqlite3.connect(os.path.join(db_path, db_file)) as opened_db:
        print("\t\tImporting database schema.")
        with open(schema_file, 'rt') as schema_f:
            schema = schema_f.read()

        # Aplly the schema.
        opened_db.executescript(schema)

"""
    Open DB file.
"""
def open_db():
    global opened_db

    opened_db = sqlite3.connect(os.path.join(db_path, db_file))


"""
    Add system record.
"""
def add_system(sys_name):
    curs = opened_db.cursor()

    curs.execute("INSERT INTO system(name) VALUES(?)", (sys_name,))

    opened_db.commit()

    return curs.lastrowid


"""
    Find system id.
"""
def find_system(sys_name):
    curs = opened_db.cursor()

    curs.execute("SELECT id FROM system WHERE name=?", (sys_name,))

    return curs.fetchone()


"""
    Handle system.
"""
def handle_system(sys_name):
    system = find_system(sys_name)

    if system == None:
        system = add_system(sys_name)
    else:
        system = system[0]

    #print(system)
    return system



"""
    Add command record.
"""
def add_command(command, group, sys_id):
    curs = opened_db.cursor()

    curs.execute("INSERT INTO command(command, man_group, system_id) "
                "VALUES(?,?,?)", (command, str(group), str(sys_id),))

    opened_db.commit()

    return curs.lastrowid


"""
    Find command record for correct OS.
"""
def find_command(command, group, os_id):
    curs = opened_db.cursor()

    curs.execute("SELECT id FROM command WHERE command=? AND "
                 "man_group=? AND system_id=?",
                 (command, group, os_id,))

    return curs.fetchone()

"""
    Handle adding commands, in case that command already exists
    also remove all switches which are associated with current command
"""
def handle_command(command, group, os_id):
    command_id = find_command(command, group, os_id)

    if command_id == None:
        # Command is not in database. Add it and use the new ID
        command_id = add_command(command, group, os_id)
    else:
        # Command already exists so use its record id and remove
        # all associated switches.
        command_id = command_id[0]
        delete_associated_switches(command_id)

    return command_id


"""
    Add switch record.
"""
def add_switch(switch, com_id):
    curs = opened_db.cursor()

    curs.execute("INSERT INTO switch(switch, command_id) "
                "VALUES(?,?)", (switch, str(com_id),))

    opened_db.commit()


"""
    Delete all switches associated to the particular command.=
"""
def delete_associated_switches(command_id):
    curs = opened_db.cursor()

    curs.execute("DELETE FROM switch WHERE command_id=?", (command_id,))

    opened_db.commit()


"""
    Prepare regex for getting directories which numbers are defined by
    global variables.
"""
def prepare_dir_regex():
    regex_begin = "^(?:"
    regex_end = ")$"
    regex = regex_begin

    for group_num in manpage_groups:
        regex = regex + "(?:man" + group_num + ")|"

    regex = re.sub('\|$', '', regex)
    regex = regex + regex_end

    return regex


"""
    Function that fetch all needed directory names.
"""
def get_directories():
    directories = []
    dir_regex = prepare_dir_regex()

    # Load all directories and files in /usr/share/man.
    for root, dirs, files in os.walk('/usr/share/man'):
        # Go through all directory names
        for directory in dirs:
            # Prepare regexp which match to all directories which starts by 'man'
            dirRegexp = re.compile(dir_regex)
            if dirRegexp.match(directory) is None:
                # Skip all directories which does not match regexp
                continue;

            # All directories names which match the regexp concatenate with path
            # and save them into list.
            directories.append(root + "/" + directory)
        # Do not go deeper into subdirectories.
        break

    # Return list with directories
    return directories


"""
    Function that get names of all files in 'directories'.
"""
def get_file_names(directories):
    files = []

    # Go through all directories
    for directory in directories:
        # Fetch all directories and files in current directory
        for r, d, f in os.walk(directory):
            # Go through all files.
            for ccc in f:
                # Add path to the file to the list
                files.append(r + "/" + ccc)
    # Return filled list.
    return files


"""
    Finds the name of the man page.
"""
def parse_name(content):
    # Create regular expression
    name_regex = re.compile("^([\w\.-]*)")
    # Get name of manual page
    just_name = name_regex.search(content)
    name_str = ""

    if just_name != None:
        name_str = just_name.group(1)

    return name_str

"""
    Parse number of man page group.
"""
def parse_manpage_number(path):
    # Create regular expression
    number_regex = re.compile(".*/man(\d).*")
    # Get number of manpage group
    number = number_regex.search(path)

    only_number = ""
    if number != None:
        number = number.group(1)

    return number



"""
    Parse flags from manpage which is in content parameter.
"""
def parse_one_page(content):

    # \u001B is escape character
    content = re.sub(u"\u001B\[[^-]*?;?[^-]*?m", "", content)

    # Create regular expression for getting flags from file
    flag_regex = re.compile("(?:\n?\s{1,}(-{1,2}[^-][?\w\-\+]*)(?:(?:,?\s(-{1,2}[?\w\-\+]+))|(?:.*?\s(-{1,2}[?\w-]+)))?)|(?:[\[\{](\-{1,2}[^ ]*?)[\|,\]\}](?:(\-{1,2}[^ ]*?)[\]\}])?)+")
    flag_list = flag_regex.findall(content)

    # Prepare empty list.
    parsed_flags = []
    # Create regex for checking whether flag contains at least one letter allowed in words.
    check_regexp = re.compile(".*?\w+.*?")
    # Go through all flags (flags can be in tuple.)
    for flags in flag_list:
        # Go through each tuple.
        for flag in flags:
            # Check flag.
            if check_regexp.match(flag):
                #Add flag into list.
                #print(flag)
                parsed_flags.append(flag)

    # Return flag which was found.
    return parsed_flags


"""
    Insert manpage into database.
"""
def put_manpage_into_db(os_id, man_name, number, flags_list):
    #print(os_id)
    #print(man_name)
    #print(number)
    #print(flags_list)

    command_id = handle_command(man_name, number, os_id)

    for flag in flags_list:
        add_switch(flag, command_id)



"""
    Generate output file in INI-like format.
"""
def generate_ini_file(out_file, name, flag_list):
    if name != "":
        # Print name of the tool into INI file.
        out_file.write("[" + name + "]")
        out_file.write("\n")

        # Print all flags for this command.
        for flag in flag_list:
            out_file.write(flag)
            out_file.write("\n")

        # Print empty line after each command block.
        out_file.write("\n")


def prepare_file():
    if os.path.isfile(file_name):
        os.remove(file_name)

    f = None
    # Open file for printing output.
    try:
        f = open(file_name, "a")
    except IOError, e:
        print e

    return f


"""
    Parse all manpages which are accessible by the path in 'path' parameter list.
"""
def parse_man_pages(files, os_id):
    # Define variables with tools for reading files.
    reader = "zcat "
    zipped_files = "zcat "
    not_zipped_files = "cat "

    f = prepare_file()
    # Open /dev/null/ for output of groff
    f_devnull = open(os.devnull, 'w')
    #files = []
    #files.append("/usr/share/man/man8/mount.8.gz")

    # Check all files.
    for file_path in files:
        """ zcat " + f + " | groff -mandoc -Tutf8
            SOME ERRORS OCCURE WHILE GROFF READING MANPAGES --- ADJUST LINE
        """
        # Check whether the file is zipped or not.
        zipped = re.compile(".*\.gz$")
        if zipped.match(file_path):
            reader = zipped_files
        else:
            reader = not_zipped_files


        # Check whether there is redirection. If it is then parse name from the path.
        file_name_changed = False
        check_file = subprocess.Popen(split(reader + file_path), stdout=subprocess.PIPE).communicate()[0]
        if re.match("\.so", check_file):
            file_name_changed = True

            # Create regex for getting name of file.
            reg_name = re.compile(".*/(.*?)\.\w{1,5}\.gz")
            # Parse path.
            parsed_path = reg_name.search(file_path)
            # Variable for saving name.
            man_name = None
            # If there is at least one match then save it to the variable.
            if parsed_path != None:
                man_name = parsed_path.group(1)

            # Create regex which catch new file name.
            new_file_regex = re.compile(".* (.*)")

            # Parse file.
            n_f_search = new_file_regex.search(check_file)

            # Prepare variable.
            new_file = None

            # If there is at least one match then save it to the prepared variable.
            if n_f_search != None:
                new_file = n_f_search.group(1)
                # Add .gz extension.
                new_file = new_file + ".gz"

            # Substitute old file name by new file name.
            if re.match(".*/.*", new_file):
                file_path = re.sub("/[-\.\w]*/[-\.\w]*$", "/" + new_file, file_path)
            elif re.match("[^/]*", new_file):
                file_path = re.sub("/[-\.\w]*$", "/" + new_file, file_path)

        p1 = subprocess.Popen(split(reader + file_path),
                                    stdout=subprocess.PIPE,
                                    universal_newlines=True)
        # Run these two commands connected by pipe.
        """
            Error output is redirected to /dev/null because of warnings from
            incorrectly formated manpages
        """
        output = subprocess.Popen(split("groff -E -c -mandoc -Tutf8"),
                                        stdin=p1.stdout,
                                        stdout=subprocess.PIPE,
                                        stderr=f_devnull,
                                        universal_newlines=True).communicate()[0]


        # Parse name of manpage.
        if not file_name_changed:
            man_name = parse_name(output)
            number = parse_manpage_number(file_path)
            # print(file_path)
            # print(number)

        # Get list of flags for this page
        flags_list = parse_one_page(output)

        # Generate output file in INI-like format.
        generate_ini_file(f, man_name, flags_list)

        put_manpage_into_db(os_id, man_name, number, flags_list)

    # Close file handler.
    f.close()


"""
    Main funciton.
"""
def main():
    # Get directories with manual pages
    directories = get_directories()

    # Create empty database in case that db file does not exists
    if os.path.exists(os.path.join(db_path, db_file)):
        open_db()
    else:
        create_empty_db()

    current_os_id = handle_system(os_name)

    # Get names of files.
    files = get_file_names(directories)

    # Parse man pages
    parse_man_pages(files, current_os_id)

"""
    Run main function.
"""
if __name__ == "__main__":
	main()
