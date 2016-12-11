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
from shlex import split

# Name of output file.
file_name = "./parsed_manpages.txt"


"""
    Function that fetch all needed directory names.
"""
def get_directories():
    directories = []

    # Load all directories and files in /usr/share/man.
    for root, dirs, files in os.walk('/usr/share/man'):
        # Go through all directory names
        for directory in dirs:
            # Prepare regexp which match to all directories which starts by 'man'
            dirRegexp = re.compile("man.*")
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
    Parse flags from manpage which is in content parameter.
"""
def parse_one_page(content):

    # \u001B is escape character
    content = re.sub(u"\u001B\[[^-]*?;?[^-]*?m", "", content)

    # Create regular expression for getting flags from file
    flag_regex = re.compile("(?:\n?\s{2,}(-{1,2}[^-][?\w-]*)(?:(?:,?\s(-{1,2}[?\w-]+))|(?:.*?\s(-{1,2}[?\w-]+)))?)|(?:[\[\{](\-{1,2}[^ ]*?)[\|,\]\}](?:(\-{1,2}[^ ]*?)[\]\}])?)+")
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
def parse_man_pages(files):
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
        if not file_name_changed :
            man_name = parse_name(output)

        # Get list of flags for this page
        flags_list = parse_one_page(output)

        # Generate output file in INI-like format.
        generate_ini_file(f, man_name, flags_list)

    # Close file handler.
    f.close()


"""
    Main funciton.
"""
def main():
    # Get directories with manual pages
    directories = get_directories()

    # Get names of files.
    files = get_file_names(directories)

    # Parse man pages
    parse_man_pages(files)

"""
    Run main function.
"""
if __name__ == "__main__":
	main()
