/**
 * RustChain Configuration File Parser & Validator
 * 
 * Parse and validate RustChain node configuration files.
 * Supports YAML, JSON, and TOML formats.
 */

import * as fs from 'fs';
import * as path from 'path';
import * as os from 'os';

export interface RustChainConfig {
  // Node settings
  node?: {
    host?: string;
    port?: number;
    ssl?: boolean;
    sslCert?: string;
    sslKey?: string;
  };
  
  // Network settings
  network?: {
    p2pPort?: number;
    bootstrapNodes?: string[];
    maxPeers?: number;
    enableUpnp?: boolean;
  };
  
  // Mining settings
  mining?: {
    enabled?: boolean;
    threads?: number;
    wallet?: string;
    attestation?: boolean;
    fingerprintThreshold?: number;
  };
  
  // Database settings
  database?: {
    path?: string;
    maxSize?: number;
    backupEnabled?: boolean;
  };
  
  // Logging settings
  logging?: {
    level?: 'debug' | 'info' | 'warn' | 'error';
    file?: string;
    maxFiles?: number;
  };
  
  // API settings
  api?: {
    enabled?: boolean;
    port?: number;
    cors?: boolean;
    apiKeys?: string[];
  };
}

export interface ValidationError {
  field: string;
  message: string;
  severity: 'error' | 'warning';
}

export interface ValidationResult {
  valid: boolean;
  errors: ValidationError[];
  config?: RustChainConfig;
}

/**
 * Get default config path
 */
export function getDefaultConfigPath(): string {
  const home = os.homedir();
  return path.join(home, '.rustchain', 'config.yaml');
}

/**
 * Get default config template
 */
export function getDefaultConfig(): RustChainConfig {
  return {
    node: {
      host: '0.0.0.0',
      port: 8333,
      ssl: false,
    },
    network: {
      p2pPort: 9333,
      bootstrapNodes: [
        'rtc1:seed1.rustchain.org:9333',
        'rtc1:seed2.rustchain.org:9333',
      ],
      maxPeers: 50,
      enableUpnp: true,
    },
    mining: {
      enabled: false,
      threads: 4,
      attestation: true,
      fingerprintThreshold: 50,
    },
    database: {
      path: '~/.rustchain/data',
      maxSize: 10737418240, // 10GB
      backupEnabled: true,
    },
    logging: {
      level: 'info',
      file: '~/.rustchain/logs/rustchain.log',
      maxFiles: 5,
    },
    api: {
      enabled: true,
      port: 8080,
      cors: false,
      apiKeys: [],
    },
  };
}

/**
 * Parse YAML config file
 */
export function parseYaml(content: string): any {
  // Simple YAML parser for basic key-value structures
  const lines = content.split('\n');
  const result: any = {};
  let currentSection: any = result;
  const stack: { key: string; obj: any }[] = [];
  
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i].trim();
    
    // Skip comments and empty lines
    if (!line || line.startsWith('#')) continue;
    
    // Check for section header
    const sectionMatch = line.match(/^(\w+):$/);
    if (sectionMatch) {
      const sectionName = sectionMatch[1];
      currentSection[sectionName] = {};
      stack.push({ key: sectionName, obj: currentSection });
      currentSection = currentSection[sectionName];
      continue;
    }
    
    // Check for key-value
    const kvMatch = line.match(/^(\w+):\s*(.*)$/);
    if (kvMatch) {
      const key = kvMatch[1];
      let value: any = kvMatch[2].trim();
      
      // Parse value type
      if (value === 'true' || value === 'false') {
        value = value === 'true';
      } else if (!isNaN(Number(value))) {
        value = Number(value);
      } else if (value.startsWith('"') && value.endsWith('"')) {
        value = value.slice(1, -1);
      } else if (value.startsWith("'") && value.endsWith("'")) {
        value = value.slice(1, -1);
      }
      
      currentSection[key] = value;
    }
  }
  
  return result;
}

/**
 * Parse JSON config file
 */
export function parseJson(content: string): any {
  return JSON.parse(content);
}

/**
 * Parse TOML config file
 */
export function parseToml(content: string): any {
  // Simple TOML parser for basic structures
  const lines = content.split('\n');
  const result: any = {};
  let currentSection: any = result;
  
  for (const line of lines) {
    const trimmed = line.trim();
    
    // Skip comments and empty lines
    if (!trimmed || trimmed.startsWith('#')) continue;
    
    // Section header
    if (trimmed.startsWith('[') && trimmed.endsWith(']')) {
      const sectionName = trimmed.slice(1, -1);
      result[sectionName] = {};
      currentSection = result[sectionName];
      continue;
    }
    
    // Key-value
    const kvMatch = trimmed.match(/^(\w+)\s*=\s*(.*)$/);
    if (kvMatch) {
      const key = kvMatch[1];
      let value: any = kvMatch[2].trim();
      
      // Parse value type
      if (value === 'true' || value === 'false') {
        value = value === 'true';
      } else if (!isNaN(Number(value))) {
        value = Number(value);
      } else if (value.startsWith('"') && value.endsWith('"')) {
        value = value.slice(1, -1);
      } else if (value.startsWith("'") && value.endsWith("'")) {
        value = value.slice(1, -1);
      }
      
      currentSection[key] = value;
    }
  }
  
  return result;
}

/**
 * Load config from file
 */
export function loadConfig(configPath: string): RustChainConfig {
  const ext = path.extname(configPath).toLowerCase();
  const content = fs.readFileSync(configPath, 'utf-8');
  
  switch (ext) {
    case '.yaml':
    case '.yml':
      return parseYaml(content);
    case '.json':
      return parseJson(content);
    case '.toml':
      return parseToml(content);
    default:
      // Try to detect format
      if (content.trim().startsWith('{')) {
        return parseJson(content);
      } else if (content.trim().startsWith('[')) {
        return parseToml(content);
      }
      return parseYaml(content);
  }
}

/**
 * Validate config
 */
export function validateConfig(config: RustChainConfig): ValidationResult {
  const errors: ValidationError[] = [];
  
  // Validate node settings
  if (config.node) {
    if (config.node.port !== undefined && (config.node.port < 1 || config.node.port > 65535)) {
      errors.push({ field: 'node.port', message: 'Port must be between 1 and 65535', severity: 'error' });
    }
    
    if (config.node.host !== undefined && !isValidHost(config.node.host)) {
      errors.push({ field: 'node.host', message: 'Invalid host address', severity: 'warning' });
    }
  }
  
  // Validate network settings
  if (config.network) {
    if (config.network.p2pPort !== undefined && (config.network.p2pPort < 1 || config.network.p2pPort > 65535)) {
      errors.push({ field: 'network.p2pPort', message: 'Port must be between 1 and 65535', severity: 'error' });
    }
    
    if (config.network.maxPeers !== undefined && (config.network.maxPeers < 1 || config.network.maxPeers > 1000)) {
      errors.push({ field: 'network.maxPeers', message: 'Max peers should be between 1 and 1000', severity: 'warning' });
    }
  }
  
  // Validate mining settings
  if (config.mining) {
    if (config.mining.threads !== undefined && (config.mining.threads < 1 || config.mining.threads > 128)) {
      errors.push({ field: 'mining.threads', message: 'Threads should be between 1 and 128', severity: 'warning' });
    }
    
    if (config.mining.fingerprintThreshold !== undefined && (config.mining.fingerprintThreshold < 0 || config.mining.fingerprintThreshold > 100)) {
      errors.push({ field: 'mining.fingerprintThreshold', message: 'Fingerprint threshold must be between 0 and 100', severity: 'error' });
    }
  }
  
  // Validate database settings
  if (config.database) {
    if (config.database.maxSize !== undefined && config.database.maxSize < 1048576) {
      errors.push({ field: 'database.maxSize', message: 'Minimum database size is 1MB', severity: 'warning' });
    }
  }
  
  // Validate API settings
  if (config.api) {
    if (config.api.port !== undefined && (config.api.port < 1 || config.api.port > 65535)) {
      errors.push({ field: 'api.port', message: 'Port must be between 1 and 65535', severity: 'error' });
    }
  }
  
  // Validate logging settings
  if (config.logging) {
    const validLevels = ['debug', 'info', 'warn', 'error'];
    if (config.logging.level && !validLevels.includes(config.logging.level)) {
      errors.push({ field: 'logging.level', message: `Invalid log level. Must be one of: ${validLevels.join(', ')}`, severity: 'error' });
    }
  }
  
  return {
    valid: errors.filter(e => e.severity === 'error').length === 0,
    errors,
    config,
  };
}

/**
 * Validate host string
 */
function isValidHost(host: string): boolean {
  // Check for valid IP or hostname
  const ipRegex = /^(\d{1,3}\.){3}\d{1,3}$/;
  const hostnameRegex = /^[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?(\.[a-zA-Z0-9]([a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)*$/;
  
  return ipRegex.test(host) || hostnameRegex.test(host);
}

/**
 * Generate config template
 */
export function generateTemplate(format: 'yaml' | 'json' | 'toml' = 'yaml'): string {
  const config = getDefaultConfig();
  
  switch (format) {
    case 'json':
      return JSON.stringify(config, null, 2);
    case 'toml':
      // Simple toml conversion
      let toml = '';
      for (const [section, values] of Object.entries(config)) {
        toml += `[${section}]\n`;
        for (const [key, value] of Object.entries(values as any)) {
          if (typeof value === 'string') {
            toml += `${key} = "${value}"\n`;
          } else if (Array.isArray(value)) {
            toml += `${key} = ${JSON.stringify(value)}\n`;
          } else {
            toml += `${key} = ${value}\n`;
          }
        }
        toml += '\n';
      }
      return toml;
    default:
      // YAML
      let yaml = '';
      for (const [section, values] of Object.entries(config)) {
        yaml += `${section}:\n`;
        for (const [key, value] of Object.entries(values as any)) {
          if (typeof value === 'string') {
            yaml += `  ${key}: ${value}\n`;
          } else if (Array.isArray(value)) {
            yaml += `  ${key}:\n`;
            for (const item of value) {
              yaml += `    - ${item}\n`;
            }
          } else {
            yaml += `  ${key}: ${value}\n`;
          }
        }
        yaml += '\n';
      }
      return yaml;
  }
}

// CLI Interface
import { Command } from 'commander';
import chalk from 'chalk';

const program = new Command();

program
  .name('rustchain-config')
  .description('RustChain Configuration Parser & Validator')
  .version('1.0.0');

program
  .command('validate <configFile>')
  .description('Validate a RustChain config file')
  .action((configFile) => {
    console.log(chalk.blue(`\n🔍 Validating config: ${configFile}\n`));
    
    try {
      const config = loadConfig(configFile);
      const result = validateConfig(config);
      
      if (result.valid) {
        console.log(chalk.green('✅ Configuration is valid'));
      } else {
        console.log(chalk.red('❌ Configuration has errors:'));
      }
      
      if (result.errors.length > 0) {
        console.log(chalk.yellow('\nIssues found:'));
        for (const error of result.errors) {
          const icon = error.severity === 'error' ? '❌' : '⚠️';
          console.log(`  ${icon} [${error.field}] ${error.message}`);
        }
      }
      console.log('');
    } catch (error: any) {
      console.log(chalk.red(`\n❌ Error loading config: ${error.message}\n`));
    }
  });

program
  .command('generate')
  .description('Generate default config template')
  .option('-f, --format <format>', 'Output format (yaml, json, toml)', 'yaml')
  .option('-o, --output <file>', 'Output file')
  .action((options) => {
    const template = generateTemplate(options.format);
    
    if (options.output) {
      fs.writeFileSync(options.output, template);
      console.log(chalk.green(`\n✅ Config template saved to: ${options.output}\n`));
    } else {
      console.log(chalk.blue('\n📄 Default Configuration Template:\n'));
      console.log(template);
    }
  });

program
  .command('default')
  .description('Show default config path')
  .action(() => {
    console.log(chalk.blue('\n📁 Default config path:'));
    console.log(chalk.cyan(getDefaultConfigPath()), '\n');
  });

program.parse();
