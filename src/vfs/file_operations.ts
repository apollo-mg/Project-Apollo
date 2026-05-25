/**
 * File Operations Module
 * 
 * Provides VFS-based file operations that eliminate 'Contextual Blindness' by ensuring
 * all file operations go through the VFSManager abstraction layer.
 */

import { VFSManager, StorageBackend } from './VFSManager';

/**
 * Configuration for VFS-based file operations
 */
export interface VFSConfig {
  vaultKey: string;
  defaultBackend?: StorageBackend;
}

/**
 * VFS-based file read operation
 * Eliminates context blindness by routing through VFSManager
 */
export async function file_read(
  path: string,
  config: VFSConfig
): Promise<string> {
  const vfs = new VFSManager(config.vaultKey, config.defaultBackend);
  return vfs.read(path, {
    explicitBackend: config.defaultBackend,
    securityLevel: 'standard'
  });
}

/**
 * VFS-based file write operation
 * Eliminates context blindness by routing through VFSManager
 */
export async function file_write(
  path: string,
  content: string,
  config: VFSConfig
): Promise<void> {
  const vfs = new VFSManager(config.vaultKey, config.defaultBackend);
  await vfs.write(path, content, {
    explicitBackend: config.defaultBackend,
    securityLevel: 'standard'
  });
}

/**
 * VFS-based directory listing operation
 * Eliminates context blindness by routing through VFSManager
 */
export async function list_dir(
  directory: string,
  config: VFSConfig
): Promise<string[]> {
  const vfs = new VFSManager(config.vaultKey, config.defaultBackend);
  return vfs.list(directory, {
    explicitBackend: config.defaultBackend
  });
}
