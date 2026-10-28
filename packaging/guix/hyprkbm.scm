;; guix build -f packaging/guix/hyprkbm.scm   (or add it to a channel)
(define-module (hyprkbm)
  #:use-module (guix packages)
  #:use-module (guix download)
  #:use-module (guix gexp)
  #:use-module (guix build-system gnu)
  #:use-module ((guix licenses) #:prefix license:)
  #:use-module (gnu packages bash)
  #:use-module (gnu packages lua)
  #:use-module (gnu packages python))

(define-public hyprkbm
  (package
    (name "hyprkbm")
    (version "0.1.0")
    (source
     (origin
       (method url-fetch)
       (uri (string-append "https://github.com/phos-org/hyprKBM/releases/download/v"
                           version "/hyprkbm-" version ".tar.gz"))
       (sha256 (base32 "0jbzl5v95klw3vklds1hllwazl3vd9zgnip51m4q5mn6nmm0apss"))))
    (build-system gnu-build-system)
    (arguments
     (list
      #:tests? #f
      #:make-flags #~(list (string-append "PREFIX=" #$output))
      #:phases
      #~(modify-phases %standard-phases
          (delete 'configure)
          (delete 'build)
          (add-after 'install 'wrap
            (lambda* (#:key inputs #:allow-other-keys)
              (let ((lua (dirname (search-input-file inputs "bin/lua"))))
                (for-each
                 (lambda (tool)
                   (wrap-program (string-append #$output "/lib/hyprkbm/bin/" tool)
                     `("PATH" prefix (,lua))))
                 '("hyprkbm" "hyprkbm-apply" "hyprkbm-watch"))))))))
    ;; Guix's plain `lua` is 5.3; hyprKBM needs 5.4 or 5.5.
    ;; bash-minimal is the wrappers' shell (guix lint: wrapper-inputs).
    (inputs (list bash-minimal lua-5.4 python))
    (home-page "https://github.com/phos-org/hyprKBM")
    (synopsis "Keyboard-first keybind manager for Hyprland's Lua config")
    (description
     "hyprKBM shows every keybind from hyprland.lua and its own on a keyboard,
and adds, overrides or removes binds without editing hyprland.lua.")
    (license license:expat)))

hyprkbm
