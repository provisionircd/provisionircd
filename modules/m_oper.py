"""
/oper command
"""

import re

from handle.core import IRCD, Command, Numeric, Flag, Client, Capability, Hook

try:
    import bcrypt
except ImportError:
    bcrypt = None


class OperData:
    clients = {}

    @staticmethod
    def save_original_class(client):
        if client not in OperData.clients:
            OperData.clients[client] = {}
        OperData.clients[client]["class"] = client.class_

    @staticmethod
    def get_original_class(client):
        if client not in OperData.clients or "class" not in OperData.clients[client]:
            return None
        return OperData.clients[client]["class"]


def oper_check_certfp(client):
    if client.user.oper:
        return
    fingerprint = client.get_md_value("certfp")
    for oper in [oper for oper in IRCD.configuration.opers if oper.mask.is_match(client)]:
        if fingerprint and fingerprint in oper.mask.certfp:
            msg = f"TLS fingerprint match: IRC Operator status automatically activated. [block: {oper.name}, class: {oper.operclass.name}]"
            IRCD.server_notice(client, msg)
            do_oper_up(client, oper)
            break


def oper_check_account(client):
    if client.user.oper or client.user.account == '*':
        return
    for oper in [oper for oper in IRCD.configuration.opers if oper.mask.is_match(client)]:
        if client.user.account in oper.mask.account:
            msg = f"Account match [{client.user.account}]: IRC Operator status automatically activated. [block: {oper.name}, class: {oper.operclass.name}]"
            IRCD.server_notice(client, msg)
            do_oper_up(client, oper)
            break


def restore_class(client):
    if original_class := OperData.get_original_class(client):
        client.set_class_obj(original_class)


def do_oper_up(client, oper):
    if client.user.oper or not client.local:
        return
    OperData.save_original_class(client)
    client.set_class_obj(IRCD.get_class_from_name(oper.connectclass))
    modes = 'o'
    if oper.modes:
        # Do not automatically set following modes: gqrzH
        modes += re.sub(r"[ogqrzH]", '', oper.modes)
    client.user.opermodes = ''
    for m in [m for m in modes if IRCD.get_usermode_by_flag(m) if m not in client.user.opermodes]:
        client.user.opermodes += m

    client.user.operlogin = oper.name
    client.user.operclass = oper.operclass
    client.user.oper = oper
    client.backbuffer = []

    if 's' in modes:
        for snomask in oper.snomasks:
            if IRCD.get_snomask(snomask) and snomask not in client.user.snomask:
                client.user.snomask += snomask

    client.add_user_modes(client.user.opermodes)
    client.local.flood_penalty = 0
    if oper.swhois.strip():
        client.add_swhois(line=oper.swhois[:128], tag="oper", remove_on_deoper=1)

    if 't' in client.user.modes and oper.operhost and '@' not in oper.operhost and '!' not in oper.operhost:
        operhost = oper.operhost.removeprefix('.').removesuffix('.')
        if operhost.strip():
            if client.setinfo(operhost, t="host"):
                data = f":{client.id} SETHOST :{client.user.cloakhost}"
                IRCD.send_to_servers(client, [], data)

    msg = f"*** {client.name} ({client.user.username}@{client.user.realhost}) [block: {client.user.operlogin}, operclass: {client.user.operclass.name}] is now an IRC Operator"
    IRCD.log(client, "info", "oper", "OPER_UP", msg)

    if client.user.snomask:
        client.sendnumeric(Numeric.RPL_SNOMASK, client.user.snomask)
    client.sendnumeric(Numeric.RPL_YOUREOPER)

    client.add_md("operlogin", client.user.operlogin)
    client.add_md("operclass", client.user.operclass.name)

    IRCD.new_message(client)
    if oper_channel := IRCD.get_setting("oper-auto-join"):
        if not (oper_channel_obj := IRCD.find_channel(oper_channel)):
            oper_channel_obj = IRCD.create_channel(client, oper_channel)
        oper_channel_obj.do_join(client.mtags, client)
        if oper_channel_obj.topic_time != 0:
            Command.do(client, "TOPIC", oper_channel_obj.name)
        Command.do(client, "NAMES", oper_channel_obj.name)

    data = f":{client.name} UMODE +o"
    IRCD.send_to_local_common_chans(client, [], "oper-notify", data)


def oper_fail(client, opername, reason):
    client.local.flood_penalty += 350000
    client.sendnumeric(Numeric.ERR_NOOPERHOST)
    msg = f"Failed oper attempt by {client.name} [{opername}] ({client.user.username}@{client.user.realhost}): {reason}"
    IRCD.log(client, "warn", "oper", "OPER_FAILED", msg)


def cmd_oper(client, recv):
    if client.user.oper:
        return
    if not (oper := IRCD.configuration.get_oper(recv[1])):
        oper_fail(client, recv[1], "username not found")
        return

    if oper.password and len(recv) > 2:
        if oper.password.startswith("$2b$") and len(oper.password) > 58:
            password = recv[2].encode("utf-8")  # Bytes password, plain.
            hashed = oper.password.encode("utf-8")  # Bytes password, hashed.
            if bcrypt is not None and not bcrypt.checkpw(password, hashed):
                oper_fail(client, recv[1], "incorrect password")
                return

        elif recv[2] != oper.password:
            oper_fail(client, recv[1], "incorrect password")
            return

    for m in oper.requiredmodes:
        if m not in client.user.modes and m not in "+-":
            oper_fail(client, recv[1], "mode requirement not met")
            return

    if not oper.mask.is_match(client):
        oper_fail(client, recv[1], "mask does not match")
        return

    total_classes = [c for c in Client.table if c.user and c.local and c.class_ == oper.connectclass]
    if len(total_classes) >= int(IRCD.configuration.get_class(oper.connectclass).max):
        oper_fail(client, recv[1], "associated oper class has reached its maximum instances")
        return

    do_oper_up(client, oper)


def watch_deoper(client, target, current_modes, new_modes, param):
    if 'o' in current_modes and 'o' not in new_modes and target.local:
        """ Only show -o for oper-notify """
        data = f":{target.name} UMODE -o"
        IRCD.send_to_local_common_chans(client, [], client_cap="oper-notify", data=data)
        restore_class(target)
        target.user.operclass = None
        target.user.operlogin = None
        target.user.oper = None
        for swhois in list(target.user.swhois):
            if swhois.remove_on_deoper or swhois.tag == "oper":
                target.del_swhois(swhois.line)

        target.del_md("operlogin")


def oper_new_connection(client):
    if client.user.oper:
        return
    oper_check_certfp(client)
    oper_check_account(client)


def oper_join(client, channel):
    if 'o' in client.user.modes and client.user.operlogin:
        data = f":{client.fullmask} UMODE +o"
        IRCD.send_to_local_common_chans(client, [], client_cap="oper-notify", data=data)


def operdata_clean(client, reason):
    if client in OperData.clients:
        del OperData.clients[client]


def oper_services_synced(server):
    if not server.is_service:
        return
    for client in IRCD.local_users():
        oper_check_account(client)


def init(module):
    Command.add(module, cmd_oper, "OPER", 1, Flag.CMD_USER)
    Capability.add("oper-notify")
    Hook.add(Hook.UMODE_CHANGE, watch_deoper)
    Hook.add(Hook.LOCAL_CONNECT, oper_new_connection)
    Hook.add(Hook.LOCAL_JOIN, oper_join)
    Hook.add(Hook.LOCAL_QUIT, operdata_clean)
    Hook.add(Hook.SERVER_SYNCED, oper_services_synced)
