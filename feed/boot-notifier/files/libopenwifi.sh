#!/bin/ash

PROTOCOL=0.1

user_del() {
  local user="$1"
  local tmp

  if ! user_exists "$user" ; then
    return 0;
  fi

  [ -n "$IPKG_INSTROOT" ] || lock /var/lock/passwd
  tmp=$(mktemp /tmp/userdel_XXXXXX)

  # remove generatepw user
  cp /etc/shadow $tmp
  grep -v "^generatepw:" $tmp > /etc/shadow
  cp /etc/passwd $tmp
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
  . /etc/openwrt_release

  localaddress=$(ip r g "${address}" | head -n1 | awk '{ print $5 }')
  user=root
  password="$(dd if=/dev/urandom of=- bs=512 count=1 2>/dev/null | md5sum - | cut -c1-16)"

  user_add generatepw 1023 65534
  echo -e "$password\n$password\n" | passwd generatepw
  cryptpw="$(grep ^generatepw: /etc/shadow | awk -F: '{print $2}')"
  user_del generatepw
  uci set rpcd.@login[0].password="$cryptpw"

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
            \"password\": \"${password}\", \
            }, \
        \"method\": \"device_register\", \
        \"jsonrpc\": \"2.0\" }" \
        "http://${address}/api"
  RET=$?
}

# check if device is already registered
device_check_registered() {
  local uuid="$1"

  RESPONSE=$(wget -q -O- \
      --header='Content-Type: application/json' \
      --post-data="\
        {\"params\": \
          { \
            \"uuid\":\"${uuid}\", \
          } \
        \"method\": \"device_register\", \
        \"jsonrpc\": \"2.0\" }" \
      "http://${address}/api")
}

# check if server $1 is a openwifi server
device_discover_server() {
  local server="$1"

  RESPONSE=$(wget -q -O- \
      --header='Content-Type: application/json' \
      --post-data="\
        {\"params\": \
          { \
          }, \
        \"method\": \"hello\", \
        \"jsonrpc\": \"2.0\" }" \
      "http://${address}/api")
  if [ "$RESPONSE" = "openwifi" ] ; then
    return 1
  fi

  return 0
}
