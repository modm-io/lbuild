# Configuration

Even though *lbuild* can be configured sorely via the command line, it is
strongly recommended to create a configuration file (default is `project.xml`)
which *lbuild* will search for in the current working directory.

```xml
<library>
  <repositories>
    <!-- Declare all your repository locations relative to this file here -->
    <repository><path>path/to/repo.lb</path></repository>
    <!-- You can also use environment variables in all nodes -->
    <repository><path>${PROJECTHOME}/repo2.lb</path></repository>
    <!-- You can also search for repository files -->
    <glob>ext/**/repo.lb</glob>
  </repositories>
  <!-- You can also inherit from another configfile. The options you specify
       here will be overwritten. -->
  <extends>path/to/config.xml</extends>
  <!-- A repository may provide aliases for configurations, so that you can
       use a string as well, instead of a path. This saves you from knowing
       exactly where the configuration file is stored in the repo.
       See also `repo.add_configuration(...)`. -->
  <extends>repo:name_of_config</extends>
  <!-- A configuration alias may also be versioned -->
  <extends>repo:name_of_config:specific_version</extends>
  <!-- You can declare the *where* the output should be generated, default is cwd -->
  <outpath>generated/folder</outpath>
  <options>
    <!-- Options are treated as key-value pairs -->
    <option name="repo:repo_option_name">value</option>
    <!-- You can also use the value attribute -->
    <option name="repo:other_option_name" value="value"/>
    <!-- An option set is the only one allowing multiple values -->
    <option name="repo:module:module_option_name">set, options, may, contain, commas</option>
  </options>
  <modules>
    <!-- You only need to declare the modules you are actively using.
         The dependencies are automatically resolved by lbuild. -->
    <module>repo:module</module>
    <module>repo:other_module:submodule</module>
  </modules>
</library>
```

On startup, *lbuild* will search the current working directory upwards for one or more
`lbuild.xml` files, which if found, are used as the base configuration, inherited
by all other configurations. This is very useful when several projects all
require the same repositories, and you don't want to specify each repository
path for each project.

```xml
<library>
  <repositories>
    <repository><path>path/to/common/repo.lb</path></repository>
  </repositories>
  <modules>
    <module>repo:module-required-by-all</module>
  </modules>
</library>
```

In the simplest case your project just `<extends>` this base config.

```xml
<library>
  <extends>repo:config-name</extends>
</library>
```


## Remote Repositories

*lbuild* can clone repositories from Git into a cache folder, which defaults to
`.lbuild_cache` next to the configuration file. Use `{cache}` in the repository
path to reference the cache folder, which requires declaring it explicitly:

```xml
<library>
  <repositories>
    <cache>.lbuild_cache</cache>
    <repository>
      <vcs>
        <git>
          <!-- Folder name inside the cache folder -->
          <name>modm</name>
          <url>https://github.com/modm-io/modm.git</url>
          <!-- Optionally check out a branch or a specific commit -->
          <branch>develop</branch>
          <!-- <commit>a1b2c3d</commit> -->
        </git>
      </vcs>
      <path>{cache}/modm/repo.lb</path>
    </repository>
  </repositories>
</library>
```

Call `lbuild init` to clone the repositories including their submodules, and
`lbuild update` to fetch and fast-forward them to the latest changes.
