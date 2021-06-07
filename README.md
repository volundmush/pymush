# PyMUSH - A Barebones MUSH Framework for Python

## WARNING: Early Alpha!
Pardon our dust, this project is still in its infancy. It kinda runs, but if you're not a developer intent on sprucing it up, it may not have much for you just yet.

## CONTACT INFO
**Name:** Volund

**Email:** volundmush@gmail.com

**PayPal:** volundmush@gmail.com

**Discord:** Volund#1206  

**Discord Channel:** https://discord.gg/Sxuz3QNU8U

**Patreon:** https://www.patreon.com/volund

**Home Repository:** https://github.com/volundmush/pymush

## TERMS AND CONDITIONS

MIT license. In short: go nuts, but give credit where credit is due.

Please see the included LICENSE.txt for the legalese.

## INTRO
Building off the solid MU* framework provided by [Athanor](https://github.com/volundmush/athanor) and taking full advantage of the ANSI formatting magic of [mudstring](https://github.com/volundmush/mudstring-python) , PyMUSH is the 'next level up' for those desiring to create whole new MU* experiences.

PyMUSH provides a game architecture and scripting engine based off the principles of MUSH - see [TinyMUSH](https://github.com/TinyMUSH/TinyMUSH) , [PennMUSH](https://github.com/pennmush/pennmush) and [RhostMUSH](https://github.com/rhostmush/trunk) for some examples - without committing entirely to the MUSH way of handling permissions and building.

PyMUSH implements its own dialect of MUSHcode, however, and does not care much about backwards compatability. MUSHcode is a very cantankerous language, and the PyMUSH ideal is to modernize it as much as possible while still retaining its core advantages: being flexible, and easy to maintain using a standard MU* client.

As with Athanor, however, PyMUSH is not a fully-fledged game. This library lacks a database for persistence, and further lacks much of the itty-bitty details of most MUSHes (such as object FLAGs). Instead, PyMUSH provides a versatile API upon which to hang those features. It tries not to be too opinionated about how it might be used, or what kind of games it might be used to make.

For a more bells-and-whistles, batteries-included project built upon PyMUSH, the flagship [vmush](https://github.com/volundmush/vmush) might be of interest.

## Architecture
**Connections:** Courtesy of Athanor, Each client connection results in a Connection object. These are homogenized into a single API, regardless of their source protocol.

**GameSession:** A GameSession object represents a logged-in user who has chosen their character to play. Multiple Connections can be linked to a GameSession, and GameSessions are highly customizable - such as a replaceable prompt handler, to various ways of handling both graceful and unexpected disconnections/logouts.

**GameObject:** Everything from a player character, to user accounts, to a room or an exit is a GameObject, with a unique object ID. GameObjects have Attributes, their (optional) Location is another GameObject, they have owners (usually an Account), and can inherit Attributes (and thus, code) from their optional parent/ancestor chain. As GameObject types are simply Python Classes, creating new ones (or replacing existing ones) is easy.

**The Queue:** The Command Queue/Action Queue/Task Queue (once we decide what to call it) is a first-in, first-out (FIFO) queue that tracks all actions to be undertaken by game entities - whether this is a command entered by a client, or a script triggered by the game itself. Tasks are one-or-more commands that share the same parser instance/variables, used for both handling user commands and implementing the in-game scripting language - MUSHCode.

**Commands:** Commands are implemented in either Python or by setting a @cmd match to an Attribute on a GameObject, and implementing them as a script comprised of other commands. Python Commands are bundled up (or generated!) by **CommandMatchers**, and - in addition to simply adding more Python paths to the game's config files - replaceable APIs on various classes allow for much flexibility in determining what commands are available to who, when.

**Functions:** MUSHCode functions are implemented in Python, or aimed at a specific <gameobject>'s Attribute to call via scripting. Functions are a key element of the integrated scripting engine. Combined with Commands, this allows MUSHcode virtually unlimited ability to modify the game's state from within the game itself.

## OKAY, BUT HOW DO I USE IT?
Glad you asked!

You can install pymush using ```pip install pymush```

This adds the `pymush` command to your shell. use `pymush --help` to see what it can do.

The way that athanor and projects built on it work:

`pymush --init <folder>` will create a folder that contains your game's configuration, save files, database, and possibly some code. Enter the folder and use `pymush start` and `pymush stop` to control it. you can use `--app server` or `--app portal` to start/stop specific programs.

Examine the appdata/config.py and portal.py and server.py - which get their initial configuration from pymush's defaults - for how to change the server's configuration around.

Again, though, it doesn't do much...

## OKAAAAAAY, SO HOW DO I -REALLY- USE IT?
As with Athanor that it's built atop of, The true power of PyMUSH is in its extendability. Because you can replace any and all classes the program uses for its startup routines, and the launcher itself is a class, it's easy-peasy to create a whole new library with its own command-based launcher and game template that the launcher creates a skeleton of with `--init <folder>`.

Not gonna lie though - that does need some Python skills.

If you're looking for a project already built on PyMUSH for you, check out [vmush](https://github.com/volundmush/vmush) and don't let the MUSH in the name fool you - it's built for MUDs too!

## FAQ 
  __Q:__ This is cool! How can I help?  
  __A:__ [Patreon](https://www.patreon.com/volund) support is always welcome. If you can code and have cool ideas or bug fixes, feel free to fork, edit, and pull request! Join our [discord](https://discord.gg/Sxuz3QNU8U) to really get cranking away though.

  __Q:__ I found a bug! What do I do?  
  __A:__ Post it on this GitHub's Issues tracker. I'll see what I can do when I have time. ... or you can try to fix it yourself and submit a Pull Request. That's cool too.

  __Q:__ But... I want a MUD! Where do I start making a MUD?  
  __A:__ check out [vmush](https://github.com/volundmush/vmush)

## Special Thanks
  * The [Evennia](https://www.evennia.com) Project.
  * All of my Patrons on [Patreon](https://www.patreon.com/volund).
  * Anyone who contributes to this project or my other ones.
  * The PennMUSH and RhostMUSH dev teams, especially Ashen-Shugar.