#!/usr/bin/env python3

import argparse
import json
import yaml
import os
import subprocess
import sys
import signal
import re
import syslog
import tempfile
import time
import shutil
import pprint
import logging

#logging.basicConfig(level=logging.DEBUG, format='%(asctime)s -%(levelname)s - %(message)s')

# Define the custom action class
class CustomStoreStringAction(argparse.Action):
    def __call__(self, parser, namespace, values, option_string=None):
       
        processed_value = values.strip()  # Example: Convert to uppercase and strip whitespace
        setattr(namespace, self.dest, processed_value)  # Store in the Namespace
        print(f"called with {option_string} ")



def eprint(*args, **kwargs):
    print(*args, file=sys.stderr, **kwargs)

"""
    Add a template to a file if it does not exist, if a template exists already and disabled 
    then just reenable it.
"""
def _enable_parser( file ):
     
    if not os.path.exists( file ):
        eprint(f"file {file} not found or no permission.")
        return False


    with open( file,'r' ) as f:
         raw_content = f.read()
             
    # Make sure its we are happy with the yaml/json first...
    try:
        playbook_content = yaml.safe_load(raw_content)

    except yaml.YAMLError as e:
            log_message(f"Error parsing YAML metadata: {e}")
            sys.exit(1)

    # Create a new play from start as its empty ?
    if playbook_content is None:
        eprint('Shall I create a new playbook for you?')
        return False
    
    content_lines = raw_content.splitlines()

    if os.path.basename(sys.argv[0]) in content_lines[0]:
        print('looks good')
        print(os.path.abspath(sys.argv[0]))
    
    else:
        # @@SGM we need to decide if we add a fqdn or env....
        content_lines = [f"#!/bin/env {os.path.basename(sys.argv[0])}"] + content_lines[0:]

    # Now check if the YAML has a var section already
    if playbook_content[0].get('vars'):
        
        if playbook_content[0]['vars'].get('flags'):
            pprint.pprint(playbook_content[0]['vars'].get('flags'))
            pass

    else:
        search_terms = ["tasks: ", "pre_tasks", "roles:"]

        matches = []

        for i, line in enumerate(content_lines):
            if any(term in line for term in search_terms):

                content_lines = content_lines[:i] + add_indents_to_string(
                    yaml.dump(
                        settings_template(),
                        sort_keys=True,
                        indent=4,
                    ),2).splitlines() + [''] + content_lines[i:]

                # insert here at line i
                matches.append((i, line.strip()))
                
                try:
                    with open( 'new-'+file, 'w' ) as file:
      
                        for item in content_lines:
                            file.write(f"{item}\n")  
                
                except FileNotFoundError:
                    print("Error: The specified file path does not exist.")
                except PermissionError:
                    print("Error: You do not have permission to write to this file.")
                except Exception as e:
                    print(f"An unexpected error occurred: {e}")
                                    

                break
            
        
"""
    Load metadata, either from a comment block with the meta tag or
    take it from the ansible vars in the first playbook.
    I might consinder checking all plays but not sure there would
    be a reason to do that.
"""
def load_metadata_from_self():
    
    with open(sys.argv[1], 'r') as f:
        content = f.read()

    # Use regex to capture YAML embedded after "--- METADATA ---" until "--- END METADATA ---"
    metadata_match = re.search(
        r"# --- PARSER ---\n(.*?)\n# --- END PARSER ---", 
        content, 
        re.DOTALL)
 
    if metadata_match:
        metadata_yaml = re.sub(r'^#','',metadata_match.group(1),flags=re.MULTILINE)
    
        try:
            return yaml.safe_load(metadata_yaml)
        
        except yaml.YAMLError as e:
            log_message(f"Error parsing YAML metadata: {e}")
            sys.exit(1)

    else:
        try:
            metadata_yaml = yaml.safe_load(content)
            if metadata_yaml[0].get('vars').get('flags'):
                return metadata_yaml[0].get('vars').get('flags')
       
        except yaml.YAMLError as e:
            log_message(f"Error parsing YAML metadata: {e}")
            sys.exit(1)

    log_message("No metadata found in the playbook.")
    return {}

def parse_config(m):

    playbook = m.get("playbook")    # Meta for output ?? what about kind type form?
 
    ansible_options = m.get("ansible-options")

    return 


def parse_flags(m):
    """Parse flags from the metadata."""

    if not len(m):
        return {},{}

    parser = argparse.ArgumentParser(
        prog=f"{sys.argv[1]}",
        description=f"ansible flag parser for {sys.argv[1]}",
        exit_on_error=True,
        add_help=True,
        allow_abbrev=True
        )

    # Define flags based on metadata
    
    for flag, properties in m["flags"].items():
        
        if flag.startswith('_'):  # Skip internal variables
            continue

        if type(properties) is dict:
            arg_type = None
            arg_action = None
            dest=None

            logging.debug(properties)

            """
                Add environment vars before running the target command
            """
            if properties.get('environment'):
                pass

            """ Add Raw flags to the target command
            """
            if properties.get('flags'):
                pass
            
            elif properties.get('vars'):
        
                for var in properties['vars']:
                    dest=f"'{var}': '{properties['vars'][var]}'"   ## @@SGM change to array and append array to dest

            if properties.get("type") == "bool":
       
                parser.add_argument(
                    f"--{flag}",
                    help=properties.get("help", f"{flag} not known"),
                    required=properties.get("required", None),
                    default=properties.get("default", None),
                    action="store_true"
                    )

            elif properties.get('choices'):
        
                parser.add_argument(
                    f"--{flag}",
                    help=properties.get("help", f"{flag} not known"),
                    required=properties.get("required", None),
                    default=properties.get("default", None),
                    type=str,
                    choices=properties.get("choices", None),
                    )

            else:
      
                parser.add_argument(
                    f"--{flag}",
                    help=properties.get("help", f"{flag} not known"),
                    required=properties.get("required", None),
                    default=properties.get("default", None),
                    action=CustomStoreStringAction    
                )

    parse_result = parser.parse_args(sys.argv[2:])

    return_dict = {}

    for _parg, _pvalue in vars(parse_result).items():
      
        if m['flags'][_parg].get('type') == 'bool':

            if m['flags'][_parg].get('vars'):
                if _pvalue is True:

                    for _va in m['flags'][_parg]['vars']:
                        logging.debug(f'adding: {_va} from {_parg}')
                        return_dict[_va] = m['flags'][_parg]['vars'][_va]

            else:
                logging.debug(f'adding: direct {_parg}')
                return_dict[_parg] = _pvalue


    return parse_result, return_dict

def set_env_vars(env_vars):
    """Set environment variables based on metadata."""
    for key, value in env_vars.items():
        os.environ[key] = str(value)

def disable_ctrlc():
    """Disable CTRL+C trapping if --no-ctrlc is set."""
    signal.signal(signal.SIGINT, signal.SIG_IGN)

def write_temp_requirements_file(galaxy_requirements):
    """Write galaxy requirements to a temporary file and return the file path."""
    try:
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix=".yml")
        with open(temp_file.name, 'w') as f:
            yaml.dump(galaxy_requirements, f)
        return temp_file.name
    except yaml.YAMLError as e:
        log_message(f"Error writing YAML to temporary requirements file: {e}")
        sys.exit(1)

def install_requirements(container_engine, container_image, requirements_file, roles_dir, collections_dir):
    """Install required Ansible roles and collections persistently in the container using shared volumes."""
    command = [
        container_engine, "run", "--rm",
        "-v", f"{roles_dir}:/root/.ansible/roles",
        "-v", f"{collections_dir}:/root/.ansible/collections",
        "-v", f"{os.getcwd()}:/workspace",
        "-w", "/workspace",
        container_image,
        "ansible-galaxy", "install", "-r", requirements_file,
        "--roles-path", "/root/.ansible/roles",
        "--collections-path", "/root/.ansible/collections"
    ]
    log_message("Installing Ansible requirements persistently in container...")
    subprocess.run(command, check=True)

def log_message(message):
    """Log a message to syslog based on syslog settings in the metadata."""
    #syslog.syslog(syslog_level | syslog_priority, message)#
    print(message)

def _executor_main():
    # Load metadata from the script itself
   
    metadata = load_metadata_from_self()
    
    ansible_options = metadata.get("ansible-options",{})
    hosts = metadata.get("hosts")

    log_options = metadata.get("ansible-options",{})
    

    # Parse arguments from metadata (@@SGM just pass.args?)
    args,extra_vars = parse_flags(metadata)

    # Initialize syslog with specified level and priority
    global syslog_level, syslog_priority

    syslog_level = getattr(syslog, log_options.get("syslog_level", "LOG_INFO"))
    syslog_priority = getattr(syslog, log_options.get("syslog_priority", "LOG_USER"))

    syslog.openlog(logoption=syslog.LOG_PID, facility=syslog_priority)

    # @@SGM read from config 
    ansible_navigator="ansible-navigator"
    ansible_playbook="ansible-playbook"

    # Log script arguments at start
    # log_message(f"Script called with arguments: {sys.argv[2:]}")

    # Track start time for execution timing
    start_time = time.time()

    # Disable CTRL+C trapping if --no-ctrlc is set
    if metadata.get('no_ctrlc'):
      disable_ctrlc()

    # Set environment variables if specified in metadata
    env_vars = metadata.get("environment", {})
    set_env_vars(env_vars)

    # Get any extra ansible cli flags
    ansible_options = metadata.get("ansible_options",[])

    #Still outputing log -- mystery..
    if ansible_options is not list and ansible_options is not None:
        log_message('ansible_options is not type list')
        print(f"{type(ansible_options)}")
    
    # Determine whether to use ansible-playbook or ansible-navigator
    use_ansible_navigator = metadata.get("use_ansible_navigator", False)
    use_container = metadata.get("use_container", False)
    container_engine = metadata.get("container_engine", "podman")  # Default to podman if not specified
    container_image = metadata.get("container_image", "quay.io/ansible/ansible-runner")  # Default image

    # Create a temporary directory for Ansible roles and collections
    requirements_dir = tempfile.mkdtemp()
    roles_dir = os.path.join(requirements_dir, "roles")
    collections_dir = os.path.join(requirements_dir, "collections")
    os.makedirs(roles_dir, exist_ok=True)
    os.makedirs(collections_dir, exist_ok=True)

    # Check if galaxy requirements need to be installed
    galaxy_requirements = metadata.get("galaxy_requirements", None)

    if galaxy_requirements:
        requirements_file = write_temp_requirements_file(galaxy_requirements)

        try:
            if use_container:
                # Install requirements persistently in the container
                install_requirements(container_engine, container_image, requirements_file, roles_dir, collections_dir)
            else:
                # Install requirements locally, specifying paths for roles and collections
                command = [
                    "ansible-galaxy", "install", "-r", requirements_file,
                    "--roles-path", roles_dir,
                    "--collections-path", collections_dir
                ]
                log_message("Installing Ansible requirements locally...")
                subprocess.run(command, check=True)
        finally:
            # Clean up the temporary requirements file
            if os.path.exists(requirements_file):
                os.remove(requirements_file)

    base_command = []
    
    if use_ansible_navigator:
        base_command.append ([ansible_navigator,'run'] )
    else:
         base_command.append(ansible_playbook)
          
    base_command.append( sys.argv[1] )

    if extra_vars:
            base_command.extend([ "--extra-vars", json.dumps(extra_vars) ] )

    if ansible_options is not None and len(ansible_options):
            base_command.extend(ansible_options)

    if hosts:
        if hosts == "localhost":
            base_command.extend(['-i',hosts+','])
        else:
            base_command.extend(['-i',hosts])

    # If containerized execution is enabled, wrap the command with the container engine
    if use_container:
        command = [
            container_engine, "run", "--rm",
            "-v", f"{roles_dir}:/root/.ansible/roles",  # Mount roles dir for persistent roles
            "-v", f"{collections_dir}:/root/.ansible/collections",  # Mount collections dir for persistent collections
            "-v", f"{os.getcwd()}:/workspace",
            "-w", "/workspace",
            container_image,
        ] + base_command
    else:
        command = base_command

    logging.debug(f"command={command}")

    #if args.rescuer:
    #    command.append("--rescuer-playbook")  # Run rescuer if needed

    try:
        subprocess.run(command, check=True)
        result = "SUCCESS"
    
    except subprocess.CalledProcessError as e:
        result = f"FAILED with exit code {e.returncode}"
        sys.exit(e.returncode)
    
    finally:
        # Calculate execution time and log completion
        execution_time = time.time() - start_time
        log_message(f"Execution completed in {execution_time:.2f} seconds with result: {result}")

        # Clean up the temporary requirements directory
        shutil.rmtree(requirements_dir, ignore_errors=True)

def add_indents_to_string(input_string, indent=4, indent_char=" "):
    """
    Adds a fixed number of indents to each line in the string.

    :param input_string: The original string
    :param indent: Number of characters to indent each line
    :param indent_char: Character used for indentation (default is space)
    :return: The indented string
    """
    # Split the string into lines, add indentation, and join them back
    indented_lines = [
        f"{indent_char * indent}{line}" if line.strip() else line
        for line in input_string.splitlines()
    ]
    return "\n".join(indented_lines)

def settings_template():
    
    return {
        'vars': {
            'flags': {
                'ansible_options': ['--step'],
                'environment': {'ANSIBLE_DISPLAY_ARGS_TO_STDOUT': True,
                                'ANSIBLE_ENABLE_TASK_DEBUGGER': False,
                                'ANSIBLE_INVENTORY_ENABLED': 'ini,yaml,script,host_list,auto',
                                'ANSIBLE_LOCALHOST_WARNING': False,
                                'ANSIBLE_STDOUT_CALLBACK': 'oneline',
                                'MY_ENV_VAR': 'some_value',
                                'PYTHONWARNINGS': 'ignore::UserWarning'},
                'flags': {'check': {'default': False,
                                    'flags': '-C',
                                    'help': 'Run in Check mode - no changes made',
                                    'required': False,
                                    'type': 'bool',
                                    'vars': None},
                        'env': {'choices': ['prod', 'preprod'],
                                'default': 1,
                                'help': 'Target environment',
                                'required': True},
                        'start': {'default': False,
                                    'help': 'Start the target environment',
                                    'required': False,
                                    'type': 'bool',
                                    'vars': {'start_environment': True}},
                        'stop': {'default': False,
                                    'help': 'Stop the target environment',
                                    'required': False,
                                    'type': 'bool',
                                    'vars': {'stop_environment': True}}},
                'hosts': 'localhost',
                'no_ctrlc': True,
                'rescuer': {'default': False,
                            'help': 'Execute rescuer playbook on failure',
                            'required': False}}}}

def main():
    
    parser = argparse.ArgumentParser(
        #prog=f"{sys.argv[0]}",
        description=f"ansible flag parser and stuff",
        exit_on_error=True,
        add_help=True,
        allow_abbrev=True
        )

    parser.add_argument(
        f"--enable",
        help="Enable flags in a playbook",
        action="store_true"
        )
    
    parser.add_argument(
        f"--disable",
        help="Disable flags in a playbook",
        action="store_true"
        )
    
    parser.add_argument(
        f"--encode",
        help="Encode a playbook",
        action="store_true"
        )
    
    parser.add_argument(
        f"playbook",
        help="Playbook name"
        )
      
    parse_result = parser.parse_args()

    if parse_result.enable:
       return( _enable_parser( parse_result.playbook ) )
    
    if parse_result.enable:
       return( _disable_parser( parse_result.playbook ) )
    


    

# -----------------------------------------------------------
if __name__ == "__main__":

    if len(sys.argv) > 2:
        if os.path.isfile(sys.argv[1]):
            executor_main()
        else:
            main()
    
    else:
        main()

# -----------------------------------------------------------

"""
 TODO:
    add -e mode to edit settings for a playbook then write back to the playbook
    hexify & zip the the data and store it in one line

    internal flag --int to allow for actions such as
        show where the playbook runs / docker / pod / navigator etc
        show internal non-secret settings requirements or config file location 
    
    run via suid? 
    encrypt playbook (ansible-vaulted ??)
    convert to bin !? possible to wrap in ??
    add windows/wsl support
    build/remove from playbook
      auto  lint for playbook if available
    create config file template (.ansible-flag-parser.cfg) 
          /etc/ansible-flag-parser/playbook-name{!yml}.cfg
          /etc/ansible-flag-parser/user/
          /etc/ansible-flag-parser/groups/
    allow list of flags per item?? useful ? -f --flag

"""