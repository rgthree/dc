#!/usr/bin/env -S python3

import os
import sys
import copy
import shutil
import dataclasses

import ruamel.yaml  # https://sourceforge.net/p/ruamel-yaml/code/ci/default/tree/comments.py

yaml = ruamel.yaml.YAML()


class Emitter(ruamel.yaml.emitter.Emitter):
  '''Emitter to clear out empty lines in lists.'''

  def write_comment(self, comment, pre=False):
    if comment.value.replace('\n', ''):
      ruamel.yaml.emitter.Emitter.write_comment(self, comment, pre)


yaml.Emitter = Emitter


@dataclasses.dataclass(frozen=True, kw_only=True)
class Ctx:
  """A context instance for the generation."""

  working_dir: str
  script_dir: str
  subdir: str


class colors:
  '''Colors class:reset all colors with colors.reset; two
    sub classes fg for foreground
    and bg for background; use as colors.subclass.colorname.
    i.e. colors.fg.red or colors.bg.greenalso, the generic bold, disable,
    underline, reverse, strike through,
    and invisible work with the main class i.e. colors.bold'''
  reset = '\033[0m'
  bold = '\033[01m'
  disable = '\033[02m'
  underline = '\033[04m'
  reverse = '\033[07m'
  strikethrough = '\033[09m'
  invisible = '\033[08m'

  class fg:
    black = '\033[30m'
    red = '\033[31m'
    green = '\033[32m'
    orange = '\033[33m'
    blue = '\033[34m'
    purple = '\033[35m'
    cyan = '\033[36m'
    lightgrey = '\033[37m'
    darkgrey = '\033[90m'
    lightred = '\033[91m'
    lightgreen = '\033[92m'
    yellow = '\033[93m'
    lightblue = '\033[94m'
    pink = '\033[95m'
    lightcyan = '\033[96m'

  class bg:
    black = '\033[40m'
    red = '\033[41m'
    green = '\033[42m'
    orange = '\033[43m'
    blue = '\033[44m'
    purple = '\033[45m'
    cyan = '\033[46m'
    lightgrey = '\033[47m'


def docker_compose_run(docker_args):
  '''Main program running like docker-compose.

    Use like:
        ./dc.py [DIRECTORY] [COMMAND]
        ./dc.py media/ up
        ./dc.py media/ down
        ./dc.py media/ reup
  '''
  OUTPUT_DOCKER_COMPOSE_FILE = 'generated.docker-compose.yaml'
  print(
    '%s -> Running: docker compose --file %s %s' %
    (colors.reset, OUTPUT_DOCKER_COMPOSE_FILE, ' '.join(docker_args))
  )
  print()
  os.system('docker compose --file %s %s' % (OUTPUT_DOCKER_COMPOSE_FILE, ' '.join(docker_args)))
  sys.exit(0)


def generate_docker_compose_file(ctx: Ctx):
  # Change to script directory.
  working_dir = ctx.working_dir
  subdir_relative = f'./{ctx.subdir}'
  script_dir = ctx.script_dir
  # os.chdir(script_dir)

  BASE_ENV = './base.env' if os.path.isfile('./base.env') else f'{script_dir}/base.env'
  BASE_DOCKER_COMPOSE = './base.docker-compose.yaml' if os.path.isfile(
    './base.env'
  ) else f'{script_dir}/base.docker-compose.yaml'

  X_ENV = f'{subdir_relative}/x.env'
  X_DOCKER_COMPOSE = f'{subdir_relative}/x.docker-compose.yaml'
  TPL_DOCKER_COMPOSE = f'{subdir_relative}/tpl.docker-compose.yaml'

  OUTPUT_ENV = f'{subdir_relative}/.env'
  OUTPUT_TEMP_DOCKER_COMPOSE = f'{subdir_relative}/temp.docker-compose.yaml'
  OUTPUT_DOCKER_COMPOSE_FILE = 'generated.docker-compose.yaml'
  OUTPUT_DOCKER_COMPOSE = '%s/%s' % (subdir_relative, OUTPUT_DOCKER_COMPOSE_FILE)

  GENERATED_STRING = f'This file is generated from python. Do not edit it directly.'

  # X_BASE_MIXIN_PATTERN = re.compile(r'(\s*)x-base:\s*true.*')
  # X_BASE_MIXIN_PATTERN = re.compile(r'(\s*)x-base-no-networks-for-fail2ban:\s*true.*')

  if os.path.isfile(X_ENV):
    print(
      '%s -> Generating %s by combining %s and %s' % (colors.reset, OUTPUT_ENV, BASE_ENV, X_ENV)
    )
    with open(OUTPUT_ENV, 'wb') as wfd:
      wfd.write(("# %s\n" % GENERATED_STRING).encode())
      for f in [BASE_ENV, X_ENV]:
        with open(f, 'rb') as fd:
          shutil.copyfileobj(fd, wfd)
          wfd.write("\n".encode())

  if os.path.isfile(X_DOCKER_COMPOSE):
    print(
      '%s -> Generating temporary %s by combining %s and %s' %
      (colors.reset, OUTPUT_TEMP_DOCKER_COMPOSE, BASE_DOCKER_COMPOSE, X_DOCKER_COMPOSE)
    )
    with open(OUTPUT_TEMP_DOCKER_COMPOSE, 'wb') as wfd:
      for f in [BASE_DOCKER_COMPOSE, X_DOCKER_COMPOSE]:
        with open(f, 'r') as fd:
          for line in fd:
            line = line.replace('x-base: true', '<<: *base')
            line = line.replace(
              'x-base-no-networks-for-fail2ban: true', '<<: *base-no-networks-for-fail2ban'
            )
            line = line.replace('x-base-no-user-env: true', '<<: *base-no-user-env')
            wfd.write(line.encode())
          wfd.write("\n".encode())

  if os.path.isfile(OUTPUT_TEMP_DOCKER_COMPOSE):
    print('%s -> Using temporary %s' % (colors.reset, OUTPUT_TEMP_DOCKER_COMPOSE))
    with open(OUTPUT_TEMP_DOCKER_COMPOSE) as file:
      data = yaml.load(file)
    os.remove(OUTPUT_TEMP_DOCKER_COMPOSE)
  else:
    print('%s -> Using templated %s' % (colors.reset, TPL_DOCKER_COMPOSE))
    with open(TPL_DOCKER_COMPOSE) as file:
      data = yaml.load(file)

  for service_name in data['services']:
    service = data['services'][service_name]
    print('%s -> Evaluating service: %s%s' % (colors.reset, colors.fg.orange, service_name))

    # If there's no container_name set, then set the service name to it, otherwise docker-compose
    # will append a "_1" and sometimes a prefix.
    if not 'container_name' in service:
      print('%s   -> Setting container_name to %s' % (colors.reset, service_name))
      service.insert(0, 'container_name', service_name, comment='Generated.')

    # If we have an "x-volumes" then let's take it, and extend it on our current
    # list from a potential base.
    if 'x-volumes' in service:
      print('%s   -> Combining x-volumes' % (colors.reset))
      volumes_list = copy.deepcopy(service.get('volumes', ruamel.yaml.comments.CommentedSeq()))
      volumes_list.extend(service['x-volumes'])
      service.update({'volumes': volumes_list,})
      service.pop('x-volumes')

    # If we have an "x-environment" then let's take it, and extend it on our current environment
    # list from a potential base.
    if 'x-environment' in service:
      print('%s   -> Combining x-environment' % (colors.reset))
      environment_list = copy.deepcopy(
        service.get('environment', ruamel.yaml.comments.CommentedSeq())
      )
      environment_list.extend(service['x-environment'])
      service.update({'environment': environment_list,})
      service.pop('x-environment')

    # If we have an x-traefik then lets set up all the labels.
    handle_traefik(service, 'x-traefik')
    handle_traefik(service, 'x-traefik-internal')

  print('%s -> Outputting %s' % (colors.reset, OUTPUT_DOCKER_COMPOSE))
  with open(OUTPUT_DOCKER_COMPOSE, 'wb') as fp:
    fp.write(("# %s\n" % GENERATED_STRING).encode())
    yaml.indent(mapping=2, sequence=2, offset=2)
    yaml.dump(data, fp)


def handle_traefik(service, key='x-traefik'):
  """Handles an x-traefik dict."""
  if key not in service:
    return
  print(f'{colors.reset}   -> Setting traefik labels and network for {key}')
  if not key.startswith('x-traefik'):
    raise TypeError(f'Traefik key does not start with "x-traefik": {key}')

  # Handle both a list of rulesets, or just a single dict data
  x_traefik = service[key]
  if isinstance(x_traefik, list):
    for i, rule in enumerate(x_traefik):
      if 'name' not in rule and i > 0:
        rule['name'] = str(i)
      handle_traefik_rule(service, rule)
  else:
    handle_traefik_rule(service, x_traefik)
  service.pop(key)


def handle_traefik_rule(service, rule_data: dict):
  """Handles a trafik router rule."""
  rule_name = service['container_name']
  if rule_data.get('name'):
    rule_name += f"-{rule_data.get('name')}"

  rule = rule_data.get('rule')
  if not rule:
    if rule_data.get('hosts'):
      rule = '||'.join([f'Host(`{host}`)' for host in rule_data.get('hosts', [])])
    else:
      if rule_data.get('host'):
        host = rule_data.get('host')
      else:
        domain = rule_data.get('domain', '${LAB_DOMAIN}')
        subdomain = rule_data.get('subdomain', '')
        host = f'{subdomain}.{domain}' if subdomain else domain
      rule = f'Host(`{host}`)'

  has_sso = rule_data.get('sso') or rule_data.get('traefik-forward-auth')
  middlewares = ['headers@file', 'redirect-remove-www@file']
  if has_sso:
    middlewares.append('tinyauth')  # middlewares.append('traefik-forward-auth')

  if 'additional-middlewares' in rule_data:
    middlewares.extend(rule_data['additional-middlewares'])

  labels_list = copy.deepcopy(service.get('labels', ruamel.yaml.comments.CommentedSeq()))
  if 'traefik.enable=true' not in labels_list:
    labels_list.insert(0, 'traefik.enable=true')
  is_http = rule_data.get('http')
  is_https = not is_http or rule_data.get('https')
  if is_http:
    labels_list.extend([
      f'traefik.http.routers.{rule_name}-http.rule={rule}',
      f'traefik.http.routers.{rule_name}-http.entrypoints=http',
      # 'traefik.http.routers.%s-http.middlewares=ssl-redirect@file' % service_name,
    ])

  if is_https:
    labels_list.extend([
      f'traefik.http.routers.{rule_name}.rule={rule}',
      f'traefik.http.routers.{rule_name}.entrypoints=https',
      f'traefik.http.routers.{rule_name}.tls=true',
      f'traefik.http.routers.{rule_name}.middlewares={",".join(middlewares)}',
    ])

  if 'loadbalancer-port' in rule_data:
    labels_list.extend([
      f'traefik.http.routers.{rule_name}.service={rule_name}_service',
      f'traefik.http.services.{rule_name}_service.loadbalancer.server.port={rule_data["loadbalancer-port"]}',
    ])

  networks_list = copy.deepcopy(service.get('networks', ruamel.yaml.comments.CommentedSeq()))
  if 'traefik_proxy' not in networks_list:
    networks_list.append('traefik_proxy')

  service.update({'networks': networks_list, 'labels': labels_list,})


def main(argv):
  if argv[0] in ['-h', '--help', '-?']:
    print()
    print('Run docker-compose for templated subdirectories.')
    print()
    print(
      'Run from the parent directory w/ a `base.env` and a base.docker-compose.yaml` and pass in'
      ' the subdirecty with its own `x.env` and `x.docker-compose.yaml` to create and use a'
      ' generated docker-compose file.'
    )
    print()
    print('  Usage:    dc [DIRECTORY] [DOCKER-COMPOSE COMMANDS]')
    print()
    print('  Example:  dc media/ up -d')
    print()
    return

  subdir = argv[0]
  if subdir.endswith('/'):
    subdir = subdir[:-1]

  subdir_relative = f'./{subdir}'

  if not os.path.isdir(subdir_relative):
    print(f'Error: "{subdir}" is not a directory.')
    return

  ctx = Ctx(
    working_dir=os.getcwd(), subdir=subdir, script_dir=os.path.dirname(os.path.abspath(__file__))
  )

  # Only generate if we're not pulling down.
  if argv[1] != 'down':
    generate_docker_compose_file(ctx)
    # If we just want to generate, then return.
    if argv[1] in ['gen', 'generate']:
      return

  if argv[1] == 'reup':
    argv[1] = 'up --build'

  print(f'{colors.reset} -> Changing directory to {subdir_relative}')
  os.chdir(subdir_relative)
  docker_compose_run(argv[1:])


if __name__ == "__main__":
  main(sys.argv[1:])
