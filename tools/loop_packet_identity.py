"""Packet-specific full identity callbacks. No launcher, sampler, or ready default.

Integration supplies PacketIdentity(packet_path, packet_sha256, readiness_path,
readiness_sha256, prerequisite_pins=..., journal_guard=...). The two root hashes
and prerequisite_pins MUST come from the independently accepted frozen packet,
not from the readiness document being checked. Hashes authenticate that external
acceptance; this module cannot authenticate authorship or manufacture approval.
Use admission.ValidationInputs(**validator.validation_inputs(arm)); its bound
verify_before/verify_after methods accept admission's detached callback context
and return None or raise. journal_guard(context) must attest the driver's durable
consumed one-shot journal and ordering, returning None or raising. Its source is
frozen too. It must not launch. Admission retains capacity/lease/exit ownership.

Strict packet JSON v1, all keys required:
  format:1, recipe:<admission recipe>, source_root:<absolute repository>,
  setup:<setup.py>, build_location:<build_location.py>,
  trees:{absolute directory:{files:{relative POSIX path:{sha256,size}},
                             directories:[relative POSIX directory,...]}},
  files:{absolute file:{sha256,size}}, absent:[absolute path,...],
  save_baseline:<immutable original save copy directory>,
  graphics_cache:<build/cache>, original_reference:<immutable original trace>,
  analysis_recipe:<analyzer recipe JSON>,
  schema:<witness schema>, diagnostic_files:[absolute file,...],
  deployments:{absolute deployed file:absolute immutable source file}.
Trees include all staged-source/runtime/build/content/config/module and save
input copies. Source file pins alone do not screen newly added staged sources.
Only build/cache is excluded from immutable tree comparison. Userdata is a fresh
copy of save_baseline, outside all immutable trees; it is hashed fully before and
after, but only its prelaunch contents must equal the baseline. Empty directories
are inventoried too. All individual files (including both saved preidentities)
are immutable. Ancestor links, reparse points, hardlinks and path aliases refuse.
Absent inputs need an immutable parent inventory so additions are screened in
the freshness window. External controller configs need sibling directory
coverage too. Diagnostic coverage includes the interpreter and journal guard.

Readiness JSON: {format:1, packet_sha256, prerequisites:{kind:{path,sha256,size}},
                trees:{absolute evidence directory:<full tree inventory>}}.
These evidence roots contain every acceptance and companion and exclude the
packet/readiness documents and mutable trial outputs (no circular seals).
Exactly REQUIRED_PREREQUISITES must also be independently pinned by the caller.
Each pinned acceptance JSON has exactly {format:1, kind, packet_sha256,
authority, verdict:'accepted', blockers:[], claims:{...}, evidence:{role:ref}}.
References have exactly {path,sha256,size}. All raw evidence is rehashed on both
sides. A pinned acceptance is an external review/observation/control attestation,
not a boolean supplied by a launcher. Claims schemas are enforced below. Mapping
must be independently observed before correction, never fitted to its output.
Controls must attest this exact package/diagnostic/original reference/save/tape,
500 real passes, disabled zero replays followed by SIM120,1,60/two depth-one
replays, restore verification, all common fixture settings and independent gates.
The SIM acceptance names its disabled predecessor's digest. The pin authority owns
the truth of these attestations and their raw evidence, including ordering.

prepare_identity(packet, arm) prepares battle_identity.capture plus diagnostics
from provisional inventories; it neither writes a preidentity nor checks
readiness. Save it exclusively, freeze the final packet (including both saved
identities), then obtain authentic acceptances. postidentities holds full post
captures (including mutable inventories), even on comparison failure; integration
must persist these exclusively. No receipt
here claims native readiness, loaded-code attestation or gameplay qualification.
Fatal/reference/menu/RNG/sealed-trace gates remain separate driver obligations.
"""
from contextlib import contextmanager
import hashlib
import inspect
import json
import os
from pathlib import Path
import stat
import sys
import types


ARMS = ('loop-oracle', 'loop-correction')
REQUIRED_PREREQUISITES = {
    'witness-review': 'independent-review',
    'analyzer-review': 'independent-review',
    'packet-review': 'independent-review',
    'native-mapping': 'independent-native-observation',
    'native-safety': 'independent-review',
    'disabled-control': 'independent-native-control',
    'sim-control': 'independent-native-control',
}
CONTROL_GATES = {'admission', 'process_exit', 'fatal', 'original_reference',
                 'fixture_menu_rng', 'sealed_trace', 'postidentity'}
PACKET_KEYS = ('format recipe source_root setup build_location trees files absent save_baseline '
               'graphics_cache original_reference analysis_recipe schema diagnostic_files deployments')


def require(condition, message):
    if not condition:
        raise ValueError(message)


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, separators=(',', ':'),
                                     allow_nan=False).encode()).hexdigest()


def _keys(value, names, where):
    require(type(value) is dict and set(value) == set(names.split()), where + ': schema')


def _sha(value):
    return type(value) is str and len(value) == 64 and all(c in '0123456789abcdef' for c in value)


def _id(value):
    _keys(value, 'sha256 size', 'file identity')
    require(_sha(value['sha256']) and type(value['size']) is int and value['size'] >= 0,
            'file identity: digest/size')
    return value


def checked_path(value):
    require(type(value) is str and value, 'explicit absolute path required')
    path = Path(value)
    require(path.is_absolute() and '..' not in path.parts and str(path) == value,
            'canonical absolute path required')
    for item in (path, *path.parents):
        try:
            info = item.lstat()
        except FileNotFoundError:
            continue
        require(not stat.S_ISLNK(info.st_mode) and
                not getattr(info, 'st_file_attributes', 0) & 0x400, 'linked/reparse path')
        require(not stat.S_ISREG(info.st_mode) or info.st_nlink == 1, 'hardlinked file')
    require(str(path.resolve()) == value, 'aliased path spelling')
    return path


def _stamp(info):
    return (info.st_dev, info.st_ino, info.st_size, info.st_mtime_ns, info.st_ctime_ns)


def file_id(value):
    path = checked_path(str(value))
    before = path.stat()
    require(stat.S_ISREG(before.st_mode), 'regular file required: ' + str(path))
    result = hashlib.sha256()
    with path.open('rb') as stream:
        opened = os.fstat(stream.fileno())
        # Windows path stat can report the cached directory-entry ctime while
        # handle fstat reports the current change time. Compare ctime only
        # within the same query boundary, retaining file ID/size/mtime across it.
        require(_stamp(opened)[:-1] == _stamp(before)[:-1], 'file replaced before hashing')
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            result.update(block)
        require(_stamp(os.fstat(stream.fileno())) == _stamp(opened), 'file changed while hashing')
    require(_stamp(checked_path(str(path)).stat()) == _stamp(before), 'file replaced while hashing')
    return dict(sha256=result.hexdigest(), size=before.st_size)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        require(key not in result, 'duplicate JSON key')
        result[key] = value
    return result


def read_json(path):
    path = checked_path(str(path))
    before = file_id(path)
    value = json.loads(path.read_text(encoding='utf-8'), object_pairs_hook=_pairs,
                       parse_constant=lambda value: require(False, 'nonfinite JSON'))
    require(file_id(path) == before, 'JSON changed while reading')
    return value


def inventory_tree(value, *, exclude=()):
    """Full bytes and exact names, including empty directories; no readiness claim."""
    root = checked_path(str(value))
    excluded = {checked_path(str(p)) for p in exclude}
    files, directories = {}, []

    def visit(path):
        before = checked_path(str(path)).stat()
        require(stat.S_ISDIR(before.st_mode), 'inventory directory missing')
        with os.scandir(path) as entries:
            children = sorted(entry.name for entry in entries)
        require(len({n.casefold() for n in children}) == len(children), 'case-aliased inventory')
        for name in children:
            child = checked_path(str(path / name))
            if child in excluded:
                require(child.is_dir(), 'mutable cache must be a directory')
                continue
            relative = child.relative_to(root).as_posix()
            if child.is_dir():
                directories.append(relative)
                visit(child)
            else:
                files[relative] = file_id(child)
        require(_stamp(checked_path(str(path)).stat()) == _stamp(before), 'directory changed while hashing')

    visit(root)
    return dict(files=files, directories=sorted(directories))


def _relative(value):
    require(type(value) is str and value and '\\' not in value and ':' not in value,
            'relative POSIX inventory path required')
    path = Path(value)
    require(not path.is_absolute() and '..' not in path.parts and path.as_posix() == value,
            'relative inventory path alias')
    return path


def _tree(value):
    _keys(value, 'files directories', 'tree inventory')
    require(type(value['files']) is dict and type(value['directories']) is list, 'tree inventory types')
    names = []
    for name, row in value['files'].items():
        _relative(name); _id(row); names.append(name)
    for name in value['directories']:
        _relative(name); names.append(name)
    require(len({n.casefold() for n in names}) == len(names), 'tree inventory aliases')
    require(value['directories'] == sorted(value['directories']), 'sorted directory inventory required')


def prepare_identity(packet, arm):
    """Capture prepared inputs before freezing identities; NOT a readiness API.

    Provisional files/trees must already pin the capture dependencies, sources,
    diagnostics and deployments. The final freeze adds both saved identities.
    No readiness roots or prerequisite evidence are created or inferred here.
    """
    _keys(packet, PACKET_KEYS, 'provisional packet')
    require(arm in ARMS, 'unknown arm')
    preparer = object.__new__(PacketIdentity)
    preparer._packet = json.loads(json.dumps(packet, allow_nan=False))
    return preparer.capture(arm)


class PacketIdentity:
    def __init__(self, packet_path, packet_sha256, readiness_path, readiness_sha256,
                 *, prerequisite_pins, journal_guard):
        require(_sha(packet_sha256) and _sha(readiness_sha256), 'external frozen trust hashes required')
        self.packet_path = str(checked_path(packet_path))
        self.readiness_path = str(checked_path(readiness_path))
        self.packet_sha256, self.readiness_sha256 = packet_sha256, readiness_sha256
        require(file_id(self.packet_path)['sha256'] == packet_sha256, 'frozen packet hash differs')
        self._packet = read_json(self.packet_path)
        self._pins = json.loads(json.dumps(prerequisite_pins, allow_nan=False))
        require(type(self._pins) is dict and set(self._pins) == set(REQUIRED_PREREQUISITES),
                'independently pinned prerequisite set required')
        require(inspect.isfunction(journal_guard) or inspect.ismethod(journal_guard), 'trusted journal guard required')
        self._journal_guard = journal_guard
        self._journal_source = str(checked_path(journal_guard.__code__.co_filename))
        self.postidentities = {}
        self._before = {}
        self._validate_packet()

    def _validate_packet(self):
        p = self._packet
        _keys(p, PACKET_KEYS, 'packet')
        require(type(p['format']) is int and p['format'] == 1, 'packet format')
        require(type(p['recipe']) is dict and type(p['recipe'].get('arms')) is dict and
                set(p['recipe']['arms']) == set(ARMS), 'two explicit recipe arms required')
        require(type(p['trees']) is dict and p['trees'] and type(p['files']) is dict and p['files'],
                'complete immutable inventories required')
        for path, tree in p['trees'].items():
            checked_path(path); _tree(tree)
        for path, row in p['files'].items():
            checked_path(path); _id(row)
        roots = [Path(path) for path in p['trees']]
        require(all(not a.is_relative_to(b) for a in roots for b in roots if a != b), 'overlapping inventory roots')
        require(type(p['absent']) is list and len(set(p['absent'])) == len(p['absent']), 'explicit absent paths required')
        for path in p['absent']:
            checked_path(path)
            require(any(Path(path).is_relative_to(root) for root in roots),
                    'absent input needs immutable parent coverage during admission')
        for key in ('source_root', 'setup', 'build_location', 'save_baseline', 'graphics_cache',
                    'original_reference', 'analysis_recipe', 'schema'):
            checked_path(p[key])
        source = Path(p['source_root'])
        require(Path(p['setup']) == source / 'scripts/setup.py' and
                Path(p['build_location']) == source / 'scripts/build_location.py', 'source helper binding differs')
        require(type(p['diagnostic_files']) is list and p['diagnostic_files'] and
                len(set(p['diagnostic_files'])) == len(p['diagnostic_files']), 'diagnostic inventory required')
        for path in p['diagnostic_files']:
            checked_path(path)
        require(type(p['deployments']) is dict and p['deployments'], 'explicit deployment inventory required')
        for target, origin in p['deployments'].items():
            checked_path(target); checked_path(origin)
        frozen = self._immutable_files()
        required = {self._journal_source, str(Path(__file__)), str(Path(sys.executable).resolve()),
                    p['setup'], p['build_location'],
                    p['analysis_recipe'], p['schema'], str(source / 'tools/loop_replay_admission.py'),
                    str(source / 'tools/replay_admission.py'), str(source / 'tools/analyze_loop_correction.py'),
                    str(source / 'tools/check_runtime_trial.py'), str(source / 'tests/bounded_trace_cmp.py'),
                    str(source / 'tests/test_loop_packet_identity.py')}
        require(required <= set(p['diagnostic_files']) <= set(frozen), 'diagnostic source coverage missing')
        require(p['original_reference'] in frozen, 'immutable original reference missing')
        require(set(p['deployments']) | set(p['deployments'].values()) <= set(frozen), 'deployment coverage missing')
        require(p['save_baseline'] in p['trees'] and p['trees'][p['save_baseline']]['files'],
                'immutable nonempty original save copy required')
        require(self.packet_path not in frozen and self.readiness_path not in frozen,
                'trust documents must be outside subject inventory (no circular seals)')
        for arm, row in p['recipe']['arms'].items():
            _keys(row, 'identity_path runtime build sequence cwd cmd env launcher identity_tool', 'arm')
            for key in ('identity_path', 'runtime', 'build', 'sequence', 'cwd', 'launcher', 'identity_tool'):
                checked_path(row[key])
            require(type(row['cmd']) is list and len(row['cmd']) == 3 and
                    type(row['env']) is dict and all(type(k) is str and type(v) is str for k, v in row['env'].items()),
                    'explicit command/environment required')
            checked_path(row['cmd'][0]); checked_path(row['cmd'][1])
            require(type(row['cmd'][2]) is str and row['cmd'][2].isascii() and row['cmd'][2].isdigit() and
                    int(row['cmd'][2]) > 0, 'finite positive duration required')
            require(row['cwd'] == str(Path(row['build']) / 'work') and
                    row['cmd'][1] == str(Path(row['build']) / 'binaries/13.0.5/main.elf'), 'build/main binding differs')
            require(Path(row['launcher']) == Path(row['identity_tool']).with_name('run.py'), 'capture launcher binding differs')
            require(p['graphics_cache'] == str(Path(row['build']) / 'cache'), 'only build/cache may be mutable')
            userdata = checked_path(row['env']['SSBU_USERDATA'])
            require(userdata == Path(row['identity_path']).parent / 'userdata', 'trial userdata binding differs')
            require(all(not userdata.is_relative_to(root) and not root.is_relative_to(userdata) for root in roots),
                    'writable userdata overlaps immutable inventory')
            require(all(not Path(path).is_relative_to(userdata) for path in frozen),
                    'writable userdata cannot be a frozen file input')
            needed = {row['identity_path'], row['sequence'], row['launcher'], row['identity_tool'],
                      *row['cmd'][:2], str(Path(row['build']) / 'state.json'),
                      str(Path(row['runtime']) / 'manifest.json')}
            require(needed <= set(frozen), 'arm file coverage missing')
            state = read_json(str(Path(row['build']) / 'state.json'))
            compiler = str(checked_path(state['tools']['clang']))
            require(compiler in frozen, 'compiler input coverage missing')
            for key in ('runtime', 'build'):
                require(any(Path(row[key]).is_relative_to(root) for root in roots), 'runtime/build tree coverage missing')
            for key in ('SSBU_ROMFS', 'SSBU_FONTS', 'SSBU_TZDIR', 'SSBU_NRO_BIN'):
                if key in row['env']:
                    path = checked_path(row['env'][key])
                    require(any(path.is_relative_to(root) for root in roots), 'content/module tree coverage missing')
            for key in ('SSBU_OPUS_DLL', 'SSBU_CONFIG', 'SSBU_GRAPHICS_CONFIG'):
                if key in row['env']:
                    require(str(checked_path(row['env'][key])) in frozen, 'config/file coverage missing')
            if 'SSBU_CONFIG' in row['env']:
                parent = Path(row['env']['SSBU_CONFIG']).parent
                require(any(parent.is_relative_to(root) for root in roots),
                        'controller/graphics sibling directory coverage missing')
        userdatas = [row['env']['SSBU_USERDATA'] for row in p['recipe']['arms'].values()]
        require(len(set(userdatas)) == 2, 'fresh distinct userdata required')
        require(all(not Path(path).is_relative_to(Path(p['graphics_cache'])) for path in frozen),
                'mutable cache cannot contain immutable inputs')

    def _immutable_files(self):
        result = dict(self._packet['files'])
        for root, tree in self._packet['trees'].items():
            for name, row in tree['files'].items():
                path = str(Path(root) / _relative(name))
                require(path not in result or result[path] == row, 'conflicting frozen file identities')
                result[path] = row
        require(len({os.path.normcase(p) for p in result}) == len(result), 'frozen path aliases')
        return result

    def _rehash(self, observed=None):
        p = self._packet
        report = observed if observed is not None else {}
        report.update(files={}, trees={}, absent={}, deployments={}, errors=[])
        def check(section, key, action, wanted):
            try:
                actual = action()
                report[section][key] = actual
                if actual != wanted:
                    report['errors'].append('immutable ' + {'files': 'file', 'trees': 'tree'}.get(section, section) + ' changed: ' + key)
            except Exception as error:
                report['errors'].append(section + ' ' + key + ': ' + type(error).__name__ + ': ' + str(error))
        check('files', self.packet_path, lambda: file_id(self.packet_path)['sha256'], self.packet_sha256)
        roots = [Path(path) for path in p['trees']]
        for path, wanted in p['files'].items():
            if not any(Path(path).is_relative_to(root) for root in roots):
                check('files', path, lambda path=path: file_id(path), wanted)
        for root, wanted in p['trees'].items():
            check('trees', root, lambda root=root: inventory_tree(root, exclude=(p['graphics_cache'],)), wanted)
        for path in p['absent']:
            check('absent', path, lambda path=path: checked_path(path).exists(), False)
        for target, origin in p['deployments'].items():
            check('deployments', target, lambda target=target, origin=origin: file_id(target) == file_id(origin), True)
        require(not report['errors'], '; '.join(report['errors']))

    def _ref(self, value):
        _keys(value, 'path sha256 size', 'evidence reference')
        path = str(checked_path(value['path']))
        wanted = _id({k: value[k] for k in ('sha256', 'size')})
        require(file_id(path) == wanted, 'authenticated evidence changed: ' + path)
        return path, wanted

    def _prerequisites(self):
        require(file_id(self.readiness_path)['sha256'] == self.readiness_sha256, 'readiness root changed')
        ready = read_json(self.readiness_path)
        _keys(ready, 'format packet_sha256 prerequisites trees', 'readiness')
        require(type(ready['format']) is int and ready['format'] == 1 and
                ready['packet_sha256'] == self.packet_sha256 and ready['prerequisites'] == self._pins,
                'readiness differs from independently pinned packet/prerequisites')
        files = {self.readiness_path: file_id(self.readiness_path)}
        require(type(ready['trees']) is dict and ready['trees'], 'complete prerequisite directory inventories required')
        evidence_files = {}
        outputs = [Path(row['identity_path']).parent for row in self._packet['recipe']['arms'].values()]
        for root, tree in ready['trees'].items():
            path = checked_path(root)
            _tree(tree)
            require(all(not target.is_relative_to(path) and not path.is_relative_to(target) for target in outputs) and
                    all(not Path(target).is_relative_to(path) for target in (self.packet_path, self.readiness_path)),
                    'evidence inventory overlaps trial/trust documents')
            require(inventory_tree(root) == tree, 'prerequisite tree changed')
            for name, identity in tree['files'].items():
                target = str(path / _relative(name))
                require(target not in evidence_files, 'overlapping prerequisite inventories')
                evidence_files[target] = identity
        files.update(evidence_files)
        analysis = self._analysis()
        frozen = self._immutable_files()
        for kind, authority in REQUIRED_PREREQUISITES.items():
            path, wanted = self._ref(self._pins[kind])
            require(evidence_files.get(path) == wanted and path not in frozen,
                    'prerequisite must be in authenticated external evidence inventory')
            files[path] = wanted
            receipt = read_json(path)
            _keys(receipt, 'format kind packet_sha256 authority verdict blockers claims evidence', 'prerequisite')
            require(type(receipt['format']) is int and receipt['format'] == 1 and receipt['kind'] == kind and
                    receipt['packet_sha256'] == self.packet_sha256 and receipt['authority'] == authority and
                    receipt['verdict'] == 'accepted' and receipt['blockers'] == [], 'authentic scoped acceptance required: ' + kind)
            require(type(receipt['evidence']) is dict and receipt['evidence'], 'raw prerequisite evidence missing')
            for ref in receipt['evidence'].values():
                item, identity = self._ref(ref)
                require(item != path and item != self.readiness_path and item != self.packet_path,
                        'self-referential prerequisite evidence')
                require(evidence_files.get(item) == identity, 'prerequisite companion directory coverage missing')
                require(item not in files or files[item] == identity, 'conflicting prerequisite evidence')
                files[item] = identity
            claims = receipt['claims']
            if kind == 'native-mapping':
                _keys(claims, 'basis analysis_recipe mapping reads_per_lane lane_fighters', 'native mapping')
                _id(claims['analysis_recipe'])
                require(claims['basis'] == 'independent-precorrection-native-observation' and
                        claims['analysis_recipe'] == file_id(self._packet['analysis_recipe']) and
                        digest(claims['mapping']) == digest(analysis['mapping']) and
                        digest(claims['reads_per_lane']) == digest(analysis['reads_per_lane']), 'independent mapping differs')
                require(type(claims['lane_fighters']) is list and len(claims['lane_fighters']) == 2 and
                        all(type(n) is int and n >= 0 for n in claims['lane_fighters']) and
                        len(set(claims['lane_fighters'])) == 2, 'independent lane/fighter association missing')
                require({'observation', 'analysis', 'findings'} <= set(receipt['evidence']), 'native mapping evidence incomplete')
            elif kind.endswith('-control'):
                self._control(kind, claims, receipt['evidence'])
            else:
                _keys(claims, 'scope', 'independent review')
                require(claims['scope'] == kind and {'findings', 'freeze'} <= set(receipt['evidence']),
                        'scoped independent review findings/freeze required')
        return files, tuple(ready['trees'])

    def _analysis(self):
        path = str(Path(self._packet['source_root']) / 'tools/analyze_loop_correction.py')
        module = types.ModuleType('_loop_packet_analyzer')
        module.__file__ = path
        self._exec(module, path)
        analysis = module.validate_recipe(read_json(self._packet['analysis_recipe']))
        require(file_id(self._packet['schema'])['sha256'] == analysis['schema_sha256'], 'witness schema differs')
        return analysis

    def _control(self, kind, claims, evidence):
        _keys(claims, 'runtime_manifest executable diagnostic_sha256 save_baseline sequence_file original_reference '
              'real_passes replay_depths settings gates predecessor', 'own-package control')
        row = self._packet['recipe']['arms'][ARMS[0]]
        frozen = self._immutable_files()
        for key in ('runtime_manifest', 'executable', 'sequence_file', 'original_reference'):
            _id(claims[key])
        _tree(claims['save_baseline'])
        require(_sha(claims['diagnostic_sha256']), 'control diagnostic digest required')
        require(claims['runtime_manifest'] == frozen[str(Path(row['runtime']) / 'manifest.json')] and
                claims['executable'] == frozen[row['cmd'][0]] and
                claims['diagnostic_sha256'] == digest(self._diagnostic()) and
                claims['save_baseline'] == self._packet['trees'][self._packet['save_baseline']] and
                claims['sequence_file'] == frozen[row['sequence']] and
                claims['original_reference'] == frozen[self._packet['original_reference']],
                'own-package control identity differs')
        require(type(claims['real_passes']) is int and claims['real_passes'] == 500 and
                digest(claims['replay_depths']) == digest([] if kind == 'disabled-control' else [1, 1]),
                'control requires 500R and exact replay depths')
        required = {'SSBU_RB_NET': '0', 'SSBU_RB_SIM': '0' if kind == 'disabled-control' else '120,1,60',
                    'SSBU_LS': '1', 'SSBU_RB_SIM_VERIFY': '2', 'SSBU_RB_RESTORE_VERIFY': '1',
                    'SSBU_RB_SIM_SKIP': '0', 'SSBU_RB_SIM_LITE': '0', 'SSBU_SKYLINE': '0'}
        # Keep the original setup, seed, profiles and observer choices. Loop
        # routing and output paths differ; no other fixture setting is waived.
        common = {k: v for k, v in row['env'].items() if k.startswith(('SSBU_', 'VK_', 'RECOMP_')) and
                  not k.startswith(('SSBU_RB_NET', 'SSBU_RB_LOOP')) and k not in
                  {'SSBU_RB_SIM', 'SSBU_FIGHT_HASH', 'SSBU_R1_LOG', 'SSBU_SHOT_DIR', 'SSBU_USERDATA'}}
        # Even a malformed declaration cannot override mandatory control policy.
        required = dict(common, **required)
        require(type(claims['settings']) is dict and
                all(type(k) is str and type(v) is str for k, v in claims['settings'].items()) and
                all(claims['settings'].get(k) == v for k, v in required.items()),
                'mandatory control settings differ')
        require(claims['predecessor'] == (None if kind == 'disabled-control' else self._pins['disabled-control']['sha256']),
                'SIM must bind its accepted disabled predecessor')
        require(type(claims['gates']) is dict and set(claims['gates']) == CONTROL_GATES and
                all(type(role) is str and role in evidence for role in claims['gates'].values()) and
                len(set(claims['gates'].values())) == len(CONTROL_GATES) and
                len({evidence[role]['path'] for role in claims['gates'].values()}) == len(CONTROL_GATES),
                'separate authenticated control gate evidence required')

    def _diagnostic(self):
        frozen = self._immutable_files()
        observed = {path: file_id(path) for path in self._packet['diagnostic_files']}
        require(observed == {path: frozen[path] for path in observed}, 'immutable file changed: diagnostic inventory')
        return observed

    @contextmanager
    def _battle(self, row):
        # Execute verified source bytes, never cached .pyc or ambient setup imports.
        names = ('build_location', 'setup')
        saved = {name: sys.modules.get(name) for name in names}
        old_path = sys.path[:]
        try:
            for name in names:
                path = self._packet[name]
                module = types.ModuleType(name)
                module.__file__ = path
                sys.modules[name] = module
                self._exec(module, path)
            module = types.ModuleType('_loop_packet_battle_identity')
            module.__file__ = row['identity_tool']
            self._exec(module, row['identity_tool'])
            require(Path(sys.modules['setup'].REPO) == Path(self._packet['source_root']), 'source root differs')
            frozen = self._immutable_files()
            require(all(str(Path(self._packet['source_root']) / _relative(name)) in frozen
                        for name in sys.modules['setup'].tree_files()), 'complete raw source coverage missing')
            roots = [Path(path) for path in self._packet['trees']]
            require(all(any((Path(self._packet['source_root']) / folder).is_relative_to(root) for root in roots)
                        for folder, _, _ in sys.modules['setup'].STAGE_PLAN if folder != 'tests'),
                    'staged source directory coverage missing')
            yield module
        finally:
            sys.path[:] = old_path
            for name, module in saved.items():
                if module is None:
                    sys.modules.pop(name, None)
                else:
                    sys.modules[name] = module

    def _exec(self, module, path):
        wanted = self._immutable_files()[path]
        data = checked_path(path).read_bytes()
        require(dict(sha256=hashlib.sha256(data).hexdigest(), size=len(data)) == wanted,
                'identity dependency changed before execution')
        exec(compile(data, path, 'exec'), module.__dict__)

    def capture(self, arm):
        """Full inventory preparation only; never constitutes admission/readiness."""
        require(arm in ARMS, 'unknown arm')
        row = self._packet['recipe']['arms'][arm]
        sequence = checked_path(row['sequence']).read_text(encoding='utf-8')
        require(row['env']['SSBU_SEQ'] == ' '.join(line.strip() for line in sequence.splitlines()
                                                 if line.strip() and not line.startswith('#')),
                'effective sequence differs from frozen tape')
        with self._battle(row) as battle:
            result = battle.capture(build=row['build'], runtime=row['runtime'], exe=row['cmd'][0],
                                    sequence=row['sequence'], env=row['env'], seconds=int(row['cmd'][2]))
        result.pop('identity_sha256')
        result['diagnostic'] = self._diagnostic()
        result['identity_sha256'] = digest(result)
        return result

    def validation_inputs(self, arm):
        """Declarations for ValidationInputs; no receipt/hash implies readiness."""
        require(arm in ARMS, 'unknown arm')
        files = self._immutable_files()
        files[self.packet_path] = file_id(self.packet_path)
        prerequisites, roots = self._prerequisites()
        files.update(prerequisites)
        row = self._packet['recipe']['arms'][arm]
        userdata = row['env']['SSBU_USERDATA']
        for name, identity in self._packet['trees'][self._packet['save_baseline']]['files'].items():
            files[str(Path(userdata) / name)] = identity
        return dict(recipe_sha256=digest(self._packet['recipe']),
                    identity_sha256=files[row['identity_path']]['sha256'], readiness_path=self.readiness_path,
                    files=files, directories=tuple(sorted([*self._packet['trees'], *roots, userdata])),
                    verify_before=self.verify_before, verify_after=self.verify_after)

    def _context(self, context):
        _keys(context, 'recipe arm selected validation', 'admission callback context')
        arm = context['arm']
        require(arm in ARMS and digest(context['recipe']) == digest(self._packet['recipe']) and
                digest(context['selected']) == digest(self._packet['recipe']['arms'][arm]), 'callback recipe/arm differs')
        expected = self.validation_inputs(arm)
        actual = context['validation']
        require(all(getattr(actual, name) == expected[name] for name in
                    ('recipe_sha256', 'identity_sha256', 'readiness_path', 'files', 'directories')),
                'callback frozen validation inputs differ')
        require(actual.verify_before == self.verify_before and actual.verify_after == self.verify_after,
                'callback validator substituted')
        return arm, context['selected']

    def verify_before(self, context):
        arm, row = self._context(context)
        require(arm not in self._before, 'identity callback already consumed')
        self._rehash()
        require(self._journal_guard(context) is None, 'journal guard must complete or raise')
        saved = read_json(row['identity_path'])
        actual = self.capture(arm)
        require(digest(actual) == digest(saved), 'fresh full battle/diagnostic identity differs')
        require(inventory_tree(row['env']['SSBU_USERDATA']) == self._packet['trees'][self._packet['save_baseline']],
                'initial userdata differs from immutable original save copy')
        # Every manifest file is deployed, and every diagnostic game image has an
        # explicit immutable origin, in addition to full recursive module hashes.
        manifest = read_json(str(Path(row['runtime']) / 'manifest.json'))
        frozen, deployed = self._immutable_files(), self._packet['deployments']
        for name, identity in manifest['files'].items():
            relative = _relative(name)
            origin = str(Path(row['runtime']) / relative)
            target = str(Path(row['cwd']) / relative)
            require(frozen.get(origin) == identity and deployed.get(target) == origin and
                    frozen.get(target) == identity, 'complete package deployment differs')
        require(deployed.get(row['cmd'][0]) == str(Path(row['runtime']) / 'ssbu_native.exe'), 'host alias deployment missing')
        game = str(Path(row['cwd']) / _relative(manifest['game_dll']))
        require(game in deployed and deployed[game] in self._packet['diagnostic_files'], 'diagnostic game image origin missing')
        self._before[arm] = saved

    def verify_after(self, context):
        # Rehash all immutable inputs even if a later capture/comparison fails.
        # Admission invokes this after attested nonzero exits too.
        arm = context['arm']
        require(arm in self._before and arm not in self.postidentities, 'no matching unused preidentity validation')
        observed = dict(immutable={}, errors=[])
        self.postidentities[arm] = observed
        try:
            self._rehash(observed['immutable'])
            arm, row = self._context(context)
        except Exception as error:
            observed['errors'].append(type(error).__name__ + ': ' + str(error))
            raise
        after = self.capture(arm)
        before = json.loads(json.dumps(self._before[arm]))
        stable = json.loads(json.dumps(after))
        for item in (before, stable):
            item.pop('identity_sha256')
            item['inputs'].pop('initial_userdata')
        userdata = inventory_tree(row['env']['SSBU_USERDATA'])
        cache = self._packet['graphics_cache']
        observed.update(identity=after, userdata=userdata,
            graphics_cache=inventory_tree(cache) if checked_path(cache).exists() else {'absent': True})
        require(digest(before) == digest(stable), 'full postidentity changed beyond writable userdata')
