/**
 * Virtual File System (VFS) Manager
 * 
 * Unifies access to both StandardFS (standard file system) and VaultDriver (secure storage)
 * by providing a single abstraction layer. Handles path resolution, access control,
 * and transparent routing between the two storage backends to eliminate 'Contextual
 * Blindness' and silent path-resolution errors.
 */

import { createHash } from 'crypto';
import { promises as fs } from 'fs';
import path from 'path';

/**
 * Storage backend enumeration for routing decisions
 */
export enum StorageBackend {
  StandardFS = 'standard',
  VaultDriver = 'vault'
}

/**
 * Path resolution result with metadata for transparent access
 */
export interface ResolvedPath {
  backend: StorageBackend;
  resolvedPath: string;
  accessLevel: 'read' | 'write' | 'read-write';
  metadata: StorageMetadata;
}

/**
 * Storage metadata for access control and routing
 */
export interface StorageMetadata {
  lastModified: Date;
  size: number;
  checksum: string;
  accessControl: {
    read: boolean;
    write: boolean;
    delete: boolean;
  };
}

/**
 * Error types for VFS operations
 */
export class VFSPathError extends Error {
  constructor(
    public path: string,
    public backend: StorageBackend,
    public message: string
  ) {
    super(message);
    this.name = 'VFSPathError';
  }
}

/**
 * Error for contextual blindness - when path resolution fails due to
 * missing context or ambiguous resolution
 */
export class ContextualBlindnessError extends Error {
  constructor(
    public ambiguousPath: string,
    public candidates: string[]
  ) {
    super(`Ambiguous path resolution: ${ambiguousPath} could resolve to ${candidates.join(', ')}`);
    this.name = 'ContextualBlindnessError';
  }
}

/**
 * Standard File System implementation
 */
export class StandardFS {
  private cache: Map<string, string> = new Map();

  async read(filePath: string): Promise<string> {
    const key = `standard:${filePath}`;
    if (this.cache.has(key)) {
      return this.cache.get(key)!;
    }
    
    const content = await fs.readFile(filePath, 'utf-8');
    this.cache.set(key, content);
    return content;
  }

  async write(filePath: string, content: string): Promise<void> {
    await fs.writeFile(filePath, content, 'utf-8');
    // Invalidate cache on write
    this.cache.delete(`standard:${filePath}`);
  }

  async exists(filePath: string): Promise<boolean> {
    try {
      await fs.access(filePath);
      return true;
    } catch {
      return false;
    }
  }

  async delete(filePath: string): Promise<void> {
    await fs.unlink(filePath);
    this.cache.delete(`standard:${filePath}`);
  }
}

/**
 * Secure storage implementation for sensitive data
 */
export class VaultDriver {
  private encryptionKey: string;
  private secureCache: Map<string, string> = new Map();

  constructor(key: string) {
    this.encryptionKey = key;
  }

  async read(vaultPath: string): Promise<string> {
    const key = `vault:${vaultPath}`;
    if (this.secureCache.has(key)) {
      return this.secureCache.get(key)!;
    }
    
    // Simulate secure retrieval with encryption/decryption
    const encryptedPath = this.encryptPath(vaultPath);
    const content = await this.secureRead(encryptedPath);
    this.secureCache.set(key, content);
    return content;
  }

  async write(vaultPath: string, content: string): Promise<void> {
    const encryptedPath = this.encryptPath(vaultPath);
    await this.secureWrite(encryptedPath, content);
    this.secureCache.set(`vault:${vaultPath}`, content);
  }

  async exists(vaultPath: string): Promise<boolean> {
    try {
      const encryptedPath = this.encryptPath(vaultPath);
      await fs.access(encryptedPath);
      return true;
    } catch {
      return false;
    }
  }

  private encryptPath(path: string): string {
    // Simple encryption for demonstration - in production use proper crypto
    const hash = createHash('sha256');
    return hash.update(path + this.encryptionKey).digest('hex');
  }

  private async secureRead(path: string): Promise<string> {
    // Simulate secure read with additional security checks
    return await fs.readFile(path, 'utf-8');
  }

  private async secureWrite(path: string, content: string): Promise<void> {
    await fs.writeFile(path, content, 'utf-8');
  }
}

/**
 * Virtual File System Manager - Unifies StandardFS and VaultDriver
 */
export class VFSManager {
  private standardFS: StandardFS;
  private vaultDriver: VaultDriver;
  private pathResolver: Map<string, StorageBackend> = new Map();

  constructor(
    private vaultKey: string,
    private defaultBackend: StorageBackend = StorageBackend.StandardFS
  ) {
    this.standardFS = new StandardFS();
    this.vaultDriver = new VaultDriver(vaultKey);
  }

  /**
   * Resolve a path to determine which backend should handle it
   * Eliminates 'Contextual Blindness' by providing explicit resolution
   */
  async resolvePath(
    inputPath: string,
    context?: {
      explicitBackend?: StorageBackend;
      securityLevel?: 'standard' | 'secure';
    }
  ): Promise<ResolvedPath> {
    // Explicit backend takes precedence
    if (context?.explicitBackend) {
      return this.createResolvedPath(context.explicitBackend, inputPath);
    }

    // Security level routing
    if (context?.securityLevel === 'secure') {
      return this.createResolvedPath(StorageBackend.VaultDriver, inputPath);
    }

    // Check if path exists in either backend
    const standardExists = await this.standardFS.exists(inputPath);
    const vaultExists = await this.vaultDriver.exists(inputPath);

    if (standardExists && vaultExists) {
      // Ambiguous resolution - throw ContextualBlindnessError
      throw new ContextualBlindnessError(inputPath, ['StandardFS', 'VaultDriver']);
    }

    if (standardExists) {
      return this.createResolvedPath(StorageBackend.StandardFS, inputPath);
    }

    if (vaultExists) {
      return this.createResolvedPath(StorageBackend.VaultDriver, inputPath);
    }

    // Default to configured backend
    return this.createResolvedPath(this.defaultBackend, inputPath);
  }

  private createResolvedPath(
    backend: StorageBackend,
    inputPath: string
  ): ResolvedPath {
    const resolvedPath = backend === StorageBackend.VaultDriver 
      ? `vault://${inputPath}` 
      : inputPath;

    return {
      backend,
      resolvedPath,
      accessLevel: 'read-write',
      metadata: {
        lastModified: new Date(),
        size: 0,
        checksum: '',
        accessControl: {
          read: true,
          write: true,
          delete: true
        }
      }
    };
  }

  /**
   * Read from either backend transparently
   */
  async read(
    inputPath: string,
    options?: {
      explicitBackend?: StorageBackend;
      securityLevel?: 'standard' | 'secure';
    }
  ): Promise<string> {
    const resolved = await this.resolvePath(inputPath, options);
    
    if (resolved.backend === StorageBackend.StandardFS) {
      return this.standardFS.read(resolved.resolvedPath);
    } else {
      return this.vaultDriver.read(resolved.resolvedPath);
    }
  }

  /**
   * Write to either backend transparently
   */
  async write(
    inputPath: string,
    content: string,
    options?: {
      explicitBackend?: StorageBackend;
      securityLevel?: 'standard' | 'secure';
    }
  ): Promise<void> {
    const resolved = await this.resolvePath(inputPath, options);
    
    if (resolved.backend === StorageBackend.StandardFS) {
      return this.standardFS.write(resolved.resolvedPath, content);
    } else {
      return this.vaultDriver.write(resolved.resolvedPath, content);
    }
  }

  /**
   * Check existence across both backends
   */
  async exists(inputPath: string): Promise<boolean> {
    const standardExists = await this.standardFS.exists(inputPath);
    const vaultExists = await this.vaultDriver.exists(inputPath);
    return standardExists || vaultExists;
  }

  /**
   * Delete from appropriate backend
   */
  async delete(
    inputPath: string,
    options?: {
      explicitBackend?: StorageBackend;
    }
  ): Promise<void> {
    const resolved = await this.resolvePath(inputPath, options);
    
    if (resolved.backend === StorageBackend.StandardFS) {
      return this.standardFS.delete(resolved.resolvedPath);
    } else {
      // Vault delete would be implemented similarly
      throw new Error('Delete not implemented for VaultDriver');
    }
  }

  /**
   * List files in either backend
   */
  async list(
    directory: string,
    options?: {
      explicitBackend?: StorageBackend;
    }
  ): Promise<string[]> {
    const resolved = await this.resolvePath(directory, options);
    
    if (resolved.backend === StorageBackend.StandardFS) {
      const files = await fs.readdir(resolved.resolvedPath);
      return files.map(f => path.join(resolved.resolvedPath, f));
    } else {
      // Vault listing implementation
      throw new Error('List not implemented for VaultDriver');
    }
  }
}

/**
 * Factory for creating VFSManager instances
 */
export function createVFSManager(
  vaultKey: string,
  config?: {
    defaultBackend?: StorageBackend;
  }
): VFSManager {
  return new VFSManager(vaultKey, config?.defaultBackend || StorageBackend.StandardFS);
}

// Export all types for module usage
export type { ResolvedPath, StorageMetadata, StorageBackend };
export { VFSManager, VFSPathError, ContextualBlindnessError, StandardFS, VaultDriver };
