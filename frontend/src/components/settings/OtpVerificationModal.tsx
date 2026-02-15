"use client";

import React, { useState, useEffect } from "react";
import { Modal } from "@/components/ui/Modal";
import { Button } from "@/components/ui/Button";

interface OtpVerificationModalProps {
  open: boolean;
  onClose: () => void;
  onVerify: (otp: string) => void;
  onCancel: () => void;
  maskedEmail: string;
  expiresAt: string;
  loading: boolean;
  error: string | null;
}

export function OtpVerificationModal({
  open,
  onClose,
  onVerify,
  onCancel,
  maskedEmail,
  expiresAt,
  loading,
  error,
}: OtpVerificationModalProps) {
  const [otp, setOtp] = useState("");
  const [secondsLeft, setSecondsLeft] = useState(0);

  useEffect(() => {
    if (!open) {
      setOtp("");
      return;
    }
    const updateCountdown = () => {
      const remaining = Math.max(
        0,
        Math.floor((new Date(expiresAt).getTime() - Date.now()) / 1000)
      );
      setSecondsLeft(remaining);
    };
    updateCountdown();
    const interval = setInterval(updateCountdown, 1000);
    return () => clearInterval(interval);
  }, [open, expiresAt]);

  const expired = secondsLeft <= 0;
  const minutes = Math.floor(secondsLeft / 60);
  const seconds = secondsLeft % 60;

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (otp.length === 6 && !expired) {
      onVerify(otp);
    }
  };

  return (
    <Modal open={open} onClose={onClose} title="Verify OTP" maxWidth="sm">
      <div className="space-y-4">
        <p className="text-sm text-gray-600">
          An OTP has been sent to <span className="font-medium">{maskedEmail}</span>.
          Enter it below to apply your changes.
        </p>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <input
              type="text"
              value={otp}
              onChange={(e) => {
                const val = e.target.value.replace(/\D/g, "").slice(0, 6);
                setOtp(val);
              }}
              inputMode="numeric"
              maxLength={6}
              placeholder="000000"
              disabled={expired}
              className="w-full rounded-md border border-gray-300 px-4 py-3 text-center font-mono text-2xl tracking-[0.5em] focus:border-blue-500 focus:outline-none focus:ring-1 focus:ring-blue-500 disabled:bg-gray-50 disabled:text-gray-400"
              autoFocus
            />
          </div>

          {!expired ? (
            <p className="text-center text-sm text-gray-500">
              Expires in{" "}
              <span className="font-mono font-medium">
                {minutes}:{seconds.toString().padStart(2, "0")}
              </span>
            </p>
          ) : (
            <p className="text-center text-sm text-red-600">
              OTP has expired. Please cancel and try again.
            </p>
          )}

          {error && (
            <p className="rounded-md bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </p>
          )}

          <div className="flex justify-end gap-3">
            <Button type="button" variant="secondary" onClick={onCancel} disabled={loading}>
              Cancel Request
            </Button>
            <Button
              type="submit"
              loading={loading}
              disabled={otp.length !== 6 || expired}
            >
              Verify
            </Button>
          </div>
        </form>
      </div>
    </Modal>
  );
}
