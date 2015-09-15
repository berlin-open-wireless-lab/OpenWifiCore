#
# Copyright (C) 2013-2014 OpenWrt.org
#
# This is free software, licensed under the GNU General Public License v2.
# See /LICENSE for more information.
#

include $(TOPDIR)/rules.mk

PKG_NAME:=openwifi-boot-notifier
PKG_VERSION:=2015-05-04
PKG_RELEASE=$(PKG_SOURCE_VERSION)

PKG_MAINTAINER:=Alexander Couzens <lynxis@fe80.eu>

include $(INCLUDE_DIR)/package.mk

define Package/openwifi-boot-notifier
  SECTION:=utils
  CATEGORY:=OpenWifi
  TITLE:=Boot Notifier
  DEPENDS:=+ip +rpcd +uhttpd-mod-ubus +mdns +shadow-useradd
endef

define Package/openwifi-boot-notifier/description
 Notify openwifi when booted
endef

define Build/Compile
endef

define Package/openwifi-boot-notifier/conffiles
/etc/config/openwifi
endef

define Package/openwifi-boot-notifier/install
	$(INSTALL_DIR) $(1)/lib/openwifi/
	$(INSTALL_DIR) $(1)/etc/init.d/
	$(INSTALL_DIR) $(1)/etc/config/
	$(INSTALL_BIN) ./files/openwifi-boot-notifier.init  $(1)/etc/init.d/openwifi-boot-notifier
	$(INSTALL_DATA) ./files/libopenwifi.sh $(1)/lib/openwifi/openwifi.sh
	$(INSTALL_DATA) ./files/openwifi.config $(1)/etc/config/openwifi
endef

$(eval $(call BuildPackage,openwifi-boot-notifier))
