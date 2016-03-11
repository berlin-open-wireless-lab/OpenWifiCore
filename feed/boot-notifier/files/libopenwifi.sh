#!/bin/ash

. /usr/share/libubox/jshn.sh

PROTOCOL=0.1

_log() {
  local level=$1
  shift
  logger -s -t openwifi -p daemon.$level $@
}


# register a device to the controller
device_register() {
  local server=$1
  local port=$2
  local path=$3
  local uuid=$4
  local hostname=$(uci get system.@system[0].hostname)
  local address

  address=$(nslookup "$server" 2>/dev/null | tail -n1 | awk '{print $3}')
  if [ -z "$address" ] ; then
    _log error "Could not find server"
    return 1
  fi

  . /etc/openwrt_release

  localaddress=$(ip r g "${address}" | head -n1 | awk '{ print $5 }')
  user=root
  password="$(dd if=/dev/urandom bs=512 count=1 2>/dev/null | md5sum - | cut -c1-16)"

  useradd generatepw
  echo -e "$password\n$password\n" | passwd generatepw

  uci set rpcd.@login[0].password="\$p\$generatepw"
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
        "http://${address}:${port}${path}/api"
  return $?
}

# check if device is already registered
device_is_registered() {
  local server="$1"
  local port="$2"
  local path="$3"
  local uuid="$4"

  RESPONSE=$(wget -q -O- \
      --header='Content-Type: application/json' \
      --post-data="\
        {\"params\": \
          { \
            \"uuid\":\"${uuid}\", \
          } \
        \"method\": \"device_is_registered\", \
        \"jsonrpc\": \"2.0\" }" \
      "http://${server}:${port}${path}/api")

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
  local port="$2"
  local path="$3"
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
      "http://${server}:${port}${path}/api")
  json_load "$RESPONSE"
  json_get_var result result
  if [ "$result" = "openwifi" ] ; then
    return 0
  fi

  return 1
}

# search for a openwifi controller and set it if found
device_discover() {
  if device_discover_server "openwifi" "80" ; then
    set_controller "openwifi" "80"
    return 0
  fi

  # check if mdns is available
  if ubus list mdns ; then
    local mdns controller entries ip path port
    ubus call mdns scan
    mdns=$(ubus call mdns browse)

    entries=$(jsonfilter -s "$mdns" -e '$["_openwifi._tcp"][*]')
    entries=$(echo $entries|sed s/\ //g|sed s/\}/}\ /g)
    for entry in $entries ; do
	    ip=$(jsonfilter -s "$entry" -e '$["ipv4"]')
	    path=$(jsonfilter -s "$entry" -e '$["txt"]'|sed s/path=//)
	    port=$(jsonfilter -s "$entry" -e '$["port"]')
	    if device_discover_server "$ip" "$port" "$path" ; then
		    set_controller "$ip" "$port" "$path"
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
  local port=$2
  local path=$3
  local uuid=$(uci get openwifi.@device[0].uuid)

  if ! device_register "$server" "$port" "$path" "$uuid" ; then
    return 1
  fi

  uci delete openwifi.@server[]
  uci add openwifi server
  uci set openwifi.@server[0].address="$server"
  uci set openwifi.@server[0].port="$port"
  uci set openwifi.@server[0].path="$path"
  uci commit openwifi
  return 0
}

openwifi() {
  local server port path
  local uuid
  local i=0

  while [ $i -lt 3 ] ; do
    server=$(uci get openwifi.@server[0].address)
    port=$(uci get openwifi.@server[0].port)
    path=$(uci get openwifi.@server[0].path)
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
      port=$(uci get openwifi.@device[0].port)
      path=$(uci get openwifi.@server[0].path)
    fi

    # check if server is reachable
    if ! device_discover_server "$server" "$port" "$path" ; then
      _log error "Server $server does not respond! Clear old server"
      uci delete openwifi.@server[]
      uci commit openwifi
      continue
    fi

    if ! device_is_registered "$server" "$port" "$path" "$uuid" ; then
      device_register "$server" "$port" "$path" "$uuid" && return 0
    else
      return 0
    fi
    i=$((i + 1))
    sleep 3
  done
  _log error "Could not find a suitable server or server doesn't repond"
  return 1
}
