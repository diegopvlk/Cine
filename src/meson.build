pkgdatadir = get_option('prefix') / get_option('datadir') / meson.project_name()
moduledir = pkgdatadir / 'cine'
gnome = import('gnome')

blueprints = custom_target('blueprints',
  input: files(
    'history.blp',
    'playlist.blp',
    'preferences.blp',
    'options.blp',
    'shortcuts-dialog.blp',
    'window.blp',
  ),
  output: '.',
  command: [find_program('blueprint-compiler'), 'batch-compile', '@OUTPUT@', '@CURRENT_SOURCE_DIR@', '@INPUT@'],
)

gnome.compile_resources('cine',
  'cine.gresource.xml',
  gresource_bundle: true,
  install: true,
  install_dir: pkgdatadir,
  dependencies: blueprints,
)

python = import('python')

conf = configuration_data()
conf.set('PYTHON', python.find_installation('python3').full_path())
conf.set('VERSION', meson.project_version())
conf.set('localedir', get_option('prefix') / get_option('localedir'))
conf.set('pkgdatadir', pkgdatadir)

configure_file(
  input: 'cine.in',
  output: 'cine',
  configuration: conf,
  install: true,
  install_dir: get_option('bindir'),
  install_mode: 'rwxr-xr-x'
)

cine_sources = [
  '__init__.py',
  'history.py',
  'main.py',
  'mpv_gl_area.py',
  'mpris.py',
  'options.py',
  'playlist.py',
  'preferences.py',
  'save_session.py',
  'shortcuts.py',
  'utils.py',
  'window.py',
]

install_data(cine_sources, install_dir: moduledir)
