#
# Copyright (C) 2013-2014 OpenWrt.org
#
# This is free software, licensed under the GNU General Public License v2.
# See /LICENSE for more information.
#

include $(TOPDIR)/rules.mk

PKG_NAME:=openwifi-boot-notifier
PKG_VERSION:=2014-06-10
PKG_RELEASE=$(PKG_SOURCE_VERSION)

PKG_MAINTAINER:=Alexander Couzens <lynxis@fe80.eu>

include $(INCLUDE_DIR)/package.mk

define Package/openwifi-boot-notifier
  SECTION:=utils
  CATEGORY:=OpenWifi
  TITLE:=Boot Notifier
  DEPENDS:=
endef

define Package/openwifi-boot-notifier/description
 Notify openwifi when booted
endef

define Build/Compile
endef

define Package/openwifi-boot-notifier/install
	$(INSTALL_DIR) $(1)/init.d/
	$(INSTALL_BIN) ./files/openwifi-openwifi-boot-notifier $(1)/init.d/
endef

$(eval $(call BuildPackage,openwifi-boot-notifier))
