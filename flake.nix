{
  description = "hyprKBM: a keyboard-first keybind manager for Hyprland's Lua config";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      forAll = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
    in {
      packages = forAll (pkgs: rec {
        hyprkbm = pkgs.stdenvNoCC.mkDerivation {
          pname = "hyprkbm";
          version = "0.1.0";
          src = self;

          nativeBuildInputs = [ pkgs.makeWrapper ];
          buildInputs = [ pkgs.python3 ];
          dontBuild = true;
          makeFlags = [ "PREFIX=${placeholder "out"}" ];

          # hyprctl and qs come from the user's Hyprland and Quickshell; Lua
          # and notify-send are hyprKBM's own and go on its PATH.
          postFixup = ''
            for tool in hyprkbm hyprkbm-apply hyprkbm-watch; do
              wrapProgram $out/lib/hyprkbm/bin/$tool \
                --prefix PATH : ${pkgs.lib.makeBinPath [ pkgs.lua5_4 pkgs.libnotify ]}
            done
          '';

          meta = {
            description = "Keyboard-first keybind manager for Hyprland's Lua config";
            homepage = "https://github.com/phos-org/hyprKBM";
            license = pkgs.lib.licenses.mit;
            platforms = pkgs.lib.platforms.linux;
            mainProgram = "hyprkbm";
          };
        };
        default = hyprkbm;
      });
    };
}
