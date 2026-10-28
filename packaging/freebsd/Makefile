PORTNAME=	hyprkbm
DISTVERSION=	0.1.0
CATEGORIES=	x11
MASTER_SITES=	https://github.com/phos-org/hyprKBM/releases/download/v${DISTVERSION}/

MAINTAINER=	166297224+knikou01@users.noreply.github.com
COMMENT=	Keyboard-first keybind manager for Hyprland's Lua config
WWW=		https://github.com/phos-org/hyprKBM

LICENSE=	MIT
LICENSE_FILE=	${WRKSRC}/LICENSE

RUN_DEPENDS=	hyprctl:x11-wm/hyprland

USES=		gmake lua:54,run python:run shebangfix
SHEBANG_FILES=	bin/hyprkbm bin/hyprkbm-apply bin/hyprkbm-watch
NO_ARCH=	yes
NO_BUILD=	yes
MAKE_ARGS=	PREFIX=${PREFIX} SYSTEMD=0

.include <bsd.port.mk>
