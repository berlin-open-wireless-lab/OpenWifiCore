#!/bin/ash

. /usr/share/libubox/jshn.sh

PROTOCOL=0.1

_log() {
  local level=$1
  shift
  logger -s -t openwifi -p daemon.$level $@
}

user_del() {
  local user="$1"
  local tmp

  if ! user_exists "$user" ; then
    return 0;
  fi

  [ -n "$IPKG_INSTROOT" ] || lock /var/lock/passwd
  tmp=$(mktemp /etc/shadow_XXXXXX)

  # remove generatepw user
  cp -a /etc/shadow $tmp
  grep -v "^generatepw:" $tmp > /etc/shadow
  cp -a /etc/passwd $tmp
  grep -v "^generatepw:" $tmp > /etc/passwd
  rm $tmp
  [ -n "$IPKG_INSTROOT" ] || lock -u /var/lock/passwd
}

user_set_pass() {
  local user="$1"
  if ! user_exist "$user" ; then
    return 1
  fi

  passwd "$user" <<EOF
$password
$password
EOF
  return 0;
}

# register a device to the controller
device_register() {
  local server=$1
  local uuid=$2
  local address

  address=$(nslookup "$server" 2>/dev/null | tail -n1 | awk '{print $3}')
  if [ -z "$address" ] ; then
    _log error "Could not find server"
    return 1
  fi

  . /etc/openwrt_release

  localaddress=$(ip r g "${address}" | head -n1 | awk '{ print $5 }')
  user=root
  password="$(dd if=/dev/urandom of=- bs=512 count=1 2>/dev/null | md5sum - | cut -c1-16)"

  user_add generatepw 1023 65534
  echo -e "$password\n$password\n" | passwd generatepw
  cryptpw="$(grep ^generatepw: /etc/shadow | awk -F: '{print $2}')"
  user_del generatepw
  uci set rpcd.@login[0].password="$cryptpw"
  uci commit rpcd
  _log info "Registering to server $server"

  wget -q -O/dev/null \
      --header='Content-Type: application/json' \
      --post-data="\
        {\"params\": \
          { \"uuid\":\"${uuid}\", \
            \"name\": \"${hostname}\", \
            \"address\": \"${localaddress}\", \
            \"distribution\": \"${DISTRIB_ID}\", \
            \"version\": \"${DISTRIB_RELEASE}\", \
            \"proto\": \"${PROTOCOL}\", \
            \"login\": \"${user}\", \
            \"password\": \"${password}\" \
            }, \
        \"method\": \"device_register\", \
        \"jsonrpc\": \"2.0\" }" \
        "http://${address}/api"
  return $?
}

# check if device is already registered
device_is_registered() {
  local server="$1"
  local uuid="$2"

  RESPONSE=$(wget -q -O- \
      --header='Content-Type: application/json' \
      --post-data="\
        {\"params\": \
          { \
            \"uuid\":\"${uuid}\", \
          } \
        \"method\": \"device_is_registered\", \
        \"jsonrpc\": \"2.0\" }" \
      "http://${server}/api")

  json_load "$RESPONSE"
  json_get_var result result

  if [ "$result" = "yes" ] ; then
    return 0;
  else
    return 1;
  fi
}

# check if server $1 is a openwifi server
device_discover_server() {
  local server="$1"
  local result

  RESPONSE=$(wget -q -O- \
      --header='Content-Type: application/json' \
      --post-data="\
        {\"params\": \
          { \
          }, \
        \"id\": \"23\", \
        \"method\": \"hello\", \
        \"jsonrpc\": \"2.0\" }" \
      "http://${server}/api")
  json_load "$RESPONSE"
  json_get_var result result
  if [ "$result" = "openwifi" ] ; then
    return 0
  fi

  return 1
}

# search for a openwifi controller and set it if found
device_discover() {
  if device_discover_server "openwifi" ; then
    set_controller "openwifi"
    return 0
  fi

  # check if mdns is available
  if ubus list mdns ; then
    local mdns controller
    ubus call mdns scan
    mdns=$(ubus call mdns browse)
    eval $(jsonfilter -s "$mdns" -e 'controller=@["_openwifi._tcp"]')
    for control in controller ; do
      if device_discover_server "$control" ; then
        set_controller "$control"
        return 0
      fi
    done
  fi

  return 1
}

device_generate_uuid() {
  local uuid=""

  uuid=$(cat /proc/sys/kernel/random/uuid)
  if [ -z "$uuid" ] ; then
    return 1
  fi

  uci set openwifi.@device[0].uuid="$uuid"
  uci commit openwifi
  return 0
}

# try to set the controller and register to it
set_controller() {
  local server=$1
  local uuid=$(uci get openwifi.@device[0].uuid)

  if ! device_register "$server" "$uuid" ; then
    return 1
  fi

  uci delete openwifi.@server[]
  uci add openwifi server
  uci set openwifi.@server[0].address="$server"
  uci commit openwifi
  return 0
}

openwifi() {
  local server
  local uuid
  local i=0

  while [ $i -lt 3 ] ; do
    server=$(uci get openwifi.@server[0].address)
    uuid=$(uci get openwifi.@device[0].uuid)

    # check if a uuid was generated
    if [ -z "$uuid" ] ; then
      if ! device_generate_uuid ; then
        _log error "Could not generate a uuid"
        continue
      fi
      uuid=$(uci get openwifi.@device[0].uuid)
    fi

    if [ -z "$server" ] ; then
      if ! device_discover ; then
        _log error "Could not discover a server"
        continue
      fi
      server=$(uci get openwifi.@server[0].address)
    fi

    # check if server is reachable
    if ! device_discover_server $server ; then
      _log error "Server $server does not respond! Clear old server"
      uci delete openwifi.@server[]
      uci commit openwifi
      continue
    fi

    if ! device_is_registered "$server" "$uuid" ; then
      device_register "$server" "$uuid" && return 0
    else
      return 0
    fi
    i=$((i + 1))
    sleep 3
  done
  _log error "Could not find a suitable server or server doesn't repond"
  return 1
}
