
Example with two repositories
=============================

The example provides three modules in two repositories. "module1" and
"module2" in the first repository ("repo1"), "module3" in the second
("repo2").

In the project folder, two configurations are provided: The first
("project1.xml") only builds module 2. The second one build module 1
and 3.
Module 1 can only be build for target value of "hosted". It also depends
on module 2, therefore module 2 is also included in the output.

Module 3 uses a Jinja2 template to generated the source file, the header
file is only copied to the output.
