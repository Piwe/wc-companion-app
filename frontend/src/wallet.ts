import { useCallback, useEffect, useState } from "react";

/**
 * Minimal Solana wallet hook using the injected Phantom provider (window.solana).
 *
 * This intentionally avoids the @solana/wallet-adapter dependency stack — the on-chain
 * program is not deployed yet, so we only need to read a connected address for display
 * and to scope the user's bets. Swap this for @solana/wallet-adapter-react when wiring
 * real place_bet / claim / subscribe transactions.
 */

interface PhantomProvider {
  isPhantom?: boolean;
  publicKey?: { toString(): string } | null;
  connect(opts?: { onlyIfTrusted?: boolean }): Promise<{ publicKey: { toString(): string } }>;
  disconnect(): Promise<void>;
  on(event: string, handler: (args: unknown) => void): void;
  removeListener?(event: string, handler: (args: unknown) => void): void;
}

function getProvider(): PhantomProvider | null {
  if (typeof window === "undefined") return null;
  const anyWindow = window as unknown as { solana?: PhantomProvider };
  return anyWindow.solana?.isPhantom ? anyWindow.solana : null;
}

export interface WalletState {
  publicKey: string | null;
  connecting: boolean;
  installed: boolean;
  connect: () => Promise<void>;
  disconnect: () => Promise<void>;
}

export function useWallet(): WalletState {
  const [publicKey, setPublicKey] = useState<string | null>(null);
  const [connecting, setConnecting] = useState(false);
  const [installed, setInstalled] = useState(false);

  useEffect(() => {
    const provider = getProvider();
    setInstalled(Boolean(provider));
    if (!provider) return;

    // Reconnect silently if the site was previously trusted.
    provider.connect({ onlyIfTrusted: true }).then(
      ({ publicKey: pk }) => setPublicKey(pk.toString()),
      () => undefined,
    );

    const onConnect = () => setPublicKey(getProvider()?.publicKey?.toString() ?? null);
    const onDisconnect = () => setPublicKey(null);
    provider.on("connect", onConnect);
    provider.on("disconnect", onDisconnect);
    return () => {
      provider.removeListener?.("connect", onConnect);
      provider.removeListener?.("disconnect", onDisconnect);
    };
  }, []);

  const connect = useCallback(async () => {
    const provider = getProvider();
    if (!provider) {
      window.open("https://phantom.app/", "_blank", "noopener");
      return;
    }
    setConnecting(true);
    try {
      const { publicKey: pk } = await provider.connect();
      setPublicKey(pk.toString());
    } finally {
      setConnecting(false);
    }
  }, []);

  const disconnect = useCallback(async () => {
    await getProvider()?.disconnect();
    setPublicKey(null);
  }, []);

  return { publicKey, connecting, installed, connect, disconnect };
}

export function shortAddress(addr: string): string {
  return `${addr.slice(0, 4)}…${addr.slice(-4)}`;
}
