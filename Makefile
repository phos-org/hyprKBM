# Installs hyprKBM system-wide or into a package's staging folder:
#
#   make install PREFIX=/usr DESTDIR=$pkgdir
#   make install PREFIX=/usr/local SYSTEMD=0     (no systemd, e.g. FreeBSD)
#   make dist                                     (the release tarball)
#
# make dist archives the committed HEAD: commit first, or your changes are not in it.
#
# GNU make. The tree goes to $(LIBDIR)/hyprkbm as it is in the repo: the tools
# find their files through their own real path, so the links in $(BINDIR)
# are all they need. For a per-user install from a clone, use install.sh.

PREFIX ?= /usr/local
DESTDIR ?=
BINDIR ?= $(PREFIX)/bin
LIBDIR ?= $(PREFIX)/lib
DATADIR ?= $(PREFIX)/share
SYSTEMDUSERDIR ?= $(PREFIX)/lib/systemd/user
SYSTEMDPRESETDIR ?= $(PREFIX)/lib/systemd/user-preset
SYSTEMD ?= 1
DISTDIR ?= dist

APPDIR = $(LIBDIR)/hyprkbm
TOOLS = hyprkbm hyprkbm-apply hyprkbm-watch
VERSION := $(shell sed -n 's/^__version__ = "\(.*\)"$$/\1/p' lib/hyprkbm/__init__.py)
# Every file the tools need at run time: git's list in a clone, so nothing
# untracked slips in; the unpacked release tarball has no .git, and only
# tracked files to begin with. find also covers a clone git cannot read (git
# missing, or "dubious ownership" when root builds a user's clone).
TREE = $(shell ( (test -d .git && git ls-files lib share/actions.json quickshell 2>/dev/null | grep .) \
	|| find lib share/actions.json quickshell -type f ! -path '*/__pycache__/*' ! -name '*.pyc' 2>/dev/null ) | sort)

.PHONY: all install uninstall dist

all:

install:
	@if [ -z "$(strip $(TREE))" ]; then echo "make: no files to install from lib, share and quickshell" >&2; exit 1; fi
	mkdir -p $(DESTDIR)$(APPDIR)/bin $(DESTDIR)$(BINDIR)
	for t in $(TOOLS); do \
		install -m 755 bin/$$t $(DESTDIR)$(APPDIR)/bin/$$t; \
		ln -sf $(APPDIR)/bin/$$t $(DESTDIR)$(BINDIR)/$$t; \
	done
	for f in $(TREE); do \
		mkdir -p $(DESTDIR)$(APPDIR)/$$(dirname $$f); \
		install -m 644 $$f $(DESTDIR)$(APPDIR)/$$f; \
	done
	mkdir -p $(DESTDIR)$(DATADIR)/applications
	install -m 644 share/applications/hyprkbm.desktop $(DESTDIR)$(DATADIR)/applications/
ifeq ($(SYSTEMD),1)
	mkdir -p $(DESTDIR)$(SYSTEMDUSERDIR) $(DESTDIR)$(SYSTEMDPRESETDIR)
	sed 's|%h/.local/bin|$(BINDIR)|' systemd/hyprkbm-watch.service \
		> $(DESTDIR)$(SYSTEMDUSERDIR)/hyprkbm-watch.service
	chmod 644 $(DESTDIR)$(SYSTEMDUSERDIR)/hyprkbm-watch.service
	install -m 644 systemd/80-hyprkbm.preset $(DESTDIR)$(SYSTEMDPRESETDIR)/
endif

uninstall:
	for t in $(TOOLS); do rm -f $(DESTDIR)$(BINDIR)/$$t; done
	rm -rf $(DESTDIR)$(APPDIR)
	rm -f $(DESTDIR)$(DATADIR)/applications/hyprkbm.desktop
	rm -f $(DESTDIR)$(SYSTEMDUSERDIR)/hyprkbm-watch.service
	rm -f $(DESTDIR)$(SYSTEMDPRESETDIR)/80-hyprkbm.preset

dist:
	mkdir -p $(DISTDIR)
	git archive --format=tar --prefix=hyprkbm-$(VERSION)/ HEAD \
		| gzip -n > $(DISTDIR)/hyprkbm-$(VERSION).tar.gz
	@echo $(DISTDIR)/hyprkbm-$(VERSION).tar.gz
