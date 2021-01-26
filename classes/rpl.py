from enum import Enum


class RPL(Enum):
    WELCOME = 1
    YOURHOST = 2
    CREATED = 3
    MYINFO = 4
    ISUPPORT = 5
    MAP = 6
    MAPEND = 7
    SNOMASK = 8
    BOUNCE = 10

    LUSERCLIENT = 251
    LUSEROP = 252
    LUSERUNKNOWN = 253
    LUSERCHANNELS = 254
    LUSERME = 255
    LOCALUSERS = 265
    GLOBALUSERS = 266

    AWAY = 301
    USERHOST = 302
    ISON = 303
    TEXT = 304
    ENDOFWHO = 315
    LISTSTART = 321
    LIST = 322
    LISTEND = 323
    INVITING = 341
    WHOREPLY = 352

    LINKS = 364
    ENDOFLINKS = 365

    MOTD = 372
    MOTDSTART = 375
    ENDOFMOTD = 376
    YOUREOPER = 381
    IRCOPS = 386
    ENDOFIRCOPS = 387

    LOGON = 600  # Used by WATCH
    LOGOFF = 601  # Used by WATCH


class ERR(Enum):
    NOSUCHNICK = 401
    NOSUCHSERVER = 402
    NOSUCHCHANNEL = 403
    CANNOTSENDTOCHAN = 404
    NORECIPIENT = 411
    NOTEXTTOSEND = 412
    UNKNOWNCOMMAND = 421
    SERVICESDOWN = 440
    USERNOTINCHANNEL = 441  # Target user.
    NOTONCHANNEL = 442
    USERONCHANNEL = 443  # Target already on channel.
    NOTREGISTERED = 451
    NEEDMOREPARAMS = 461
    UNKNOWNMODE = 472  # Unknown channel mode.
    NOPRIVILEGES = 481
    CHANOPRIVSNEEDED = 482  # Channel op privileges needed.
    SERVERONLY = 487
    NOOPERHOST = 491

    UMODEUNKNOWNFLAG = 501
    NOINVITE = 518
