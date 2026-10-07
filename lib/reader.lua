-- Runs a Hyprland Lua config against a recording `hl` and prints, as JSON,
-- every bind, unbind and submap it made.
--
--   lua reader.lua <entry> <config dir> <hyprKBM's keybinds.lua>
--
-- hyprctl reports Lua binds as opaque "__lua" references, so the source is the
-- only place an action can be read from. Running it, rather than parsing it,
-- is what gets loops, helper functions and `mainMod ..` right.
--
-- The config runs in a sandbox: no io, no os beyond reading the clock and the
-- environment, and files load only from the config directory. hl.on callbacks
-- are never run, and everything that asks about live state gets "nothing".
local entry, confdir, own = arg[1], arg[2], arg[3] or ""

local getinfo = debug.getinfo
local mtype = math.type

local out = { binds = {}, unbinds = {}, submaps = {} }
local seq = 0
local current_submap = ""

local function next_seq()
    seq = seq + 1
    return seq
end

local function source_of(info)
    if info.source:sub(1, 1) == "@" then return info.source:sub(2) end
    return info.short_src
end

-- The config line that called into hl: 1 is this function, 2 the hl.* function.
local function where()
    local info = getinfo(3, "Sl")
    if not info then return "?", 0 end
    return source_of(info), info.currentline
end

-- Stands in for every hl object the reader does not model (rules, timers,
-- event subscriptions, a bind's handle): any field of it, and any call on it,
-- is itself again, so `hl.bind(...):set_enabled(false)` runs and does nothing.
local INERT = setmetatable({}, {
    __index = function(self) return self end,
    __newindex = function() end,
    __call = function(self) return self end,
})

local is_dispatcher = setmetatable({}, { __mode = "k" })

-- hl.dsp and every namespace under it. Calling a node returns a description
-- of the dispatcher instead of one, which is what lets it be written back out.
local function dsp_node(path)
    return setmetatable({}, {
        __index = function(_, name)
            return dsp_node(path == "" and name or (path .. "." .. name))
        end,
        __call = function(_, ...)
            local d = { dsp = path, args = table.pack(...) }
            is_dispatcher[d] = true
            return d
        end,
    })
end

local hl = { dsp = dsp_node("") }

function hl.bind(keys, dispatcher, opts)
    local file, line = where()
    local record = { seq = next_seq(), keys = keys, submap = current_submap,
                     file = file, line = line, opts = opts }
    if type(dispatcher) == "function" then
        local info = getinfo(dispatcher, "S")
        record.dispatcher = { __function = source_of(info) .. ":" .. info.linedefined }
    elseif is_dispatcher[dispatcher] then
        record.dispatcher = dispatcher
    else
        record.dispatcher = { __opaque = true }
    end
    table.insert(out.binds, record)
    return INERT
end

function hl.unbind(keys)
    local file, line = where()
    table.insert(out.unbinds, { seq = next_seq(), keys = keys, file = file, line = line })
end

function hl.define_submap(name, reset_or_fn, fn)
    local reset = reset_or_fn
    if type(reset_or_fn) == "function" then fn, reset = reset_or_fn, nil end
    local file, line = where()
    table.insert(out.submaps, { name = name, reset = reset, file = file, line = line })
    if fn then
        local saved = current_submap
        current_submap = name
        local ok, err = pcall(fn)
        current_submap = saved
        if not ok then error(err, 0) end
    end
end

function hl.get_current_submap() return current_submap end
function hl.version() return "0.0.0" end
function hl.is_key_down() return false end
for _, name in ipairs({ "get_monitors", "get_windows", "get_workspaces", "get_layers",
                        "get_loaded_plugins", "get_workspace_windows" }) do
    hl[name] = function() return {} end
end

setmetatable(hl, {
    __index = function(_, name)
        if type(name) == "string" and name:sub(1, 4) == "get_" then
            return function() return nil end
        end
        return INERT
    end,
})

-- ------------------------------------------------------------- the sandbox

local env

local function inside_confdir(path)
    return path:sub(1, #confdir + 1) == confdir .. "/"
        and not path:find("/%.%./") and not path:find("/%.%.$")
end

local function resolve(path)
    if path:sub(1, 1) ~= "/" then return confdir .. "/" .. path end
    return path
end

local function load_config_file(path)
    -- A config that loads hyprKBM's own file would otherwise have every one of
    -- hyprKBM's binds read back as hand-written.
    if own ~= "" and path == own then return function() end end
    if not inside_confdir(path) then
        error("hyprkbm reader: refusing to load " .. path .. " (outside " .. confdir .. ")", 0)
    end
    local chunk, err = loadfile(path, "t", env)
    if not chunk then error(err, 0) end
    return chunk
end

local loaded = {}

env = {
    assert = assert, error = error, ipairs = ipairs, pairs = pairs, next = next,
    pcall = pcall, xpcall = xpcall, select = select, tonumber = tonumber,
    tostring = tostring, type = type, rawequal = rawequal, rawget = rawget,
    rawset = rawset, rawlen = rawlen, setmetatable = setmetatable,
    getmetatable = getmetatable, string = string, table = table, math = math,
    utf8 = utf8, _VERSION = _VERSION,
    print = function() end,
    os = { getenv = os.getenv, time = os.time, date = os.date, clock = os.clock },
    hl = hl,
}
env._G = env

env.dofile = function(path)
    return load_config_file(resolve(path))()
end

env.load = function(chunk, name, _, chunk_env)
    return load(chunk, name, "t", chunk_env or env)
end

env.require = function(name)
    if loaded[name] ~= nil then return loaded[name] end
    if type(name) ~= "string" or name:find("%.%.") or name:find("/") then
        error("hyprkbm reader: bad module name " .. tostring(name), 2)
    end
    local base = confdir .. "/" .. (name:gsub("%.", "/"))
    local path
    for _, candidate in ipairs({ base .. ".lua", base .. "/init.lua" }) do
        local handle = io.open(candidate, "r")
        if handle then
            handle:close()
            path = candidate
            break
        end
    end
    if not path then error("module '" .. name .. "' not found under " .. confdir, 2) end
    local result = load_config_file(path)(name)
    loaded[name] = result == nil and true or result
    return loaded[name]
end

-- ------------------------------------------------------------------ JSON

local ESCAPES = { ['"'] = '\\"', ["\\"] = "\\\\", ["\n"] = "\\n", ["\r"] = "\\r",
                  ["\t"] = "\\t", ["\b"] = "\\b", ["\f"] = "\\f" }

local function quote(s)
    return '"' .. s:gsub('[%c"\\]', function(c)
        return ESCAPES[c] or string.format("\\u%04x", c:byte())
    end) .. '"'
end

local function array_length(t)
    local n = 0
    for k in pairs(t) do
        if mtype(k) ~= "integer" or k < 1 then return nil end
        n = n + 1
    end
    for i = 1, n do
        if rawget(t, i) == nil then return nil end
    end
    return n
end

local encode

local function encode_list(values, n, depth)
    local parts = {}
    for i = 1, n do parts[i] = encode(values[i], depth + 1) end
    return "[" .. table.concat(parts, ",") .. "]"
end

encode = function(v, depth)
    depth = depth or 0
    local kind = type(v)
    if v == nil then return "null" end
    if depth > 32 then return '{"__opaque":true}' end
    if kind == "boolean" then return tostring(v) end
    if kind == "number" then
        if mtype(v) == "integer" then return string.format("%d", v) end
        if v ~= v or v == math.huge or v == -math.huge then return "null" end
        return string.format("%.17g", v)
    end
    if kind == "string" then return quote(v) end
    if kind == "function" then
        local info = getinfo(v, "S")
        return '{"__function":' .. quote(source_of(info) .. ":" .. info.linedefined) .. "}"
    end
    if kind ~= "table" or v == INERT then return '{"__opaque":true}' end
    if is_dispatcher[v] then
        return '{"dsp":' .. quote(v.dsp) .. ',"args":' .. encode_list(v.args, v.args.n, depth) .. "}"
    end
    local n = array_length(v)
    if n and n > 0 then return encode_list(v, n, depth) end
    local keys = {}
    for k in pairs(v) do table.insert(keys, k) end
    table.sort(keys, function(a, b) return tostring(a) < tostring(b) end)
    local parts = {}
    for _, k in ipairs(keys) do
        table.insert(parts, quote(tostring(k)) .. ":" .. encode(rawget(v, k), depth + 1))
    end
    return "{" .. table.concat(parts, ",") .. "}"
end

-- ------------------------------------------------------------------- run

local ok, err = xpcall(function() load_config_file(entry)() end,
                       function(e) return tostring(e) end)
if not ok then out.error = { message = err } end

io.write(encode(out), "\n")
