Name:           hyprkbm
Version:        0.1.0
Release:        0
Summary:        Keyboard-first keybind manager for Hyprland's Lua config
License:        MIT
URL:            https://github.com/phos-org/hyprKBM
Source0:        %{url}/releases/download/v%{version}/%{name}-%{version}.tar.gz
# sha256 of Source0: 0000000000000000000000000000000000000000000000000000000000000000
BuildArch:      noarch
BuildRequires:  make
BuildRequires:  systemd-rpm-macros
Requires:       hyprland >= 0.55
Requires:       python3
Requires:       (lua54 or lua55 or lua >= 5.4)
Recommends:     quickshell
Recommends:     /usr/bin/notify-send

%description
hyprKBM shows every keybind from hyprland.lua and its own on a keyboard,
and adds, overrides or removes binds without editing hyprland.lua. Binds
are applied to the running Hyprland and kept across reloads by a systemd
user service.

%prep
%autosetup

%build

%install
%make_install PREFIX=%{_prefix}

# openSUSE's %%systemd_user_post only applies the preset to units that
# %%systemd_user_pre marked, so without it the watcher is never enabled.
%pre
%if %{defined systemd_user_pre}
%systemd_user_pre hyprkbm-watch.service
%endif

%post
%systemd_user_post hyprkbm-watch.service

%preun
%systemd_user_preun hyprkbm-watch.service

%files
%license LICENSE
%doc README.md CHANGELOG.md
%{_bindir}/hyprkbm
%{_bindir}/hyprkbm-apply
%{_bindir}/hyprkbm-watch
%{_prefix}/lib/hyprkbm/
%{_datadir}/applications/hyprkbm.desktop
%{_userunitdir}/hyprkbm-watch.service
%{_userpresetdir}/80-hyprkbm.preset

%changelog
* Tue Oct 27 2026 knikou01 <166297224+knikou01@users.noreply.github.com> - 0.1.0-0
- First development release.
