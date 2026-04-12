"use client";

import { useState, useEffect } from 'react';
import { useAuth } from "@/dib/authContext";
import { PageHeader } from "@/components/shared";
import { Button } from "@/components/ui/button";

function generateProfessionalAvatar(seed: string) {
  return `https://api.dicebear.com/9.x/notionists/svg?seed=${seed}&backgroundColor=e2e8f0,f8fafc`;
}

// Generate 20 unique, deterministic seeds to create our static gallery
const AVATAR_SEEDS = Array.from({ length: 20 }, (_, i) => `corporate_user_${i + 1}`);

interface AvatarSelectorProps {
  onSelect?: (seed: string) => void; 
  initialSeed?: string | null;
}

function AvatarSelector({ onSelect, initialSeed }: AvatarSelectorProps) {
  const [selectedSeed, setSelectedSeed] = useState<string | null>(initialSeed || null);

  // Sync initial seed when it loads from storage
  useEffect(() => {
    if (initialSeed) setSelectedSeed(initialSeed);
  }, [initialSeed]);

  const handleSelect = (seed: string) => {
    setSelectedSeed(seed);
    if (onSelect) {
      onSelect(seed);
    }
  };

  return (
    <div className="w-full p-6 bg-card border border-border rounded-xl shadow-sm">
      <div className="mb-6">
        <h2 className="text-lg font-semibold text-foreground">Choose an Avatar</h2>
        <p className="text-sm text-muted-foreground">Select a profile picture to represent you in the workspace.</p>
      </div>

      <div className="grid grid-cols-4 sm:grid-cols-5 gap-4">
        {AVATAR_SEEDS.map((seed) => {
          const avatarSrc = generateProfessionalAvatar(seed);
          const isSelected = selectedSeed === seed;

          return (
            <button
              key={seed}
              onClick={() => handleSelect(seed)}
              type="button"
              className={`
                relative flex items-center justify-center rounded-full transition-all duration-200 ease-in-out
                ${isSelected 
                  ? 'ring-4 ring-primary scale-105 outline-none shadow-md' 
                  : 'ring-1 ring-border hover:ring-2 hover:ring-primary/50 hover:scale-105 hover:shadow-sm'
                }
              `}
              aria-label={`Select avatar ${seed}`}
              aria-pressed={isSelected}
            >
              <div className="w-16 h-16 sm:w-20 sm:h-20 rounded-full overflow-hidden flex items-center justify-center bg-slate-50">
                <img
                  src={avatarSrc}
                  alt={`Avatar option ${seed}`}
                  className="w-full h-full object-cover scale-[1.5]"
                />
              </div>
              
              {isSelected && (
                <div className="absolute -bottom-1 -right-1 bg-primary rounded-full p-1 border-2 border-background">
                  <svg className="w-3 h-3 text-primary-foreground" fill="none" viewBox="0 0 24 24" stroke="currentColor">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" />
                  </svg>
                </div>
              )}
            </button>
          );
        })}
      </div>
    </div>
  );
}

export function EditProfile() {
  const { user } = useAuth();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [avatarSeed, setAvatarSeed] = useState<string | null>(null);

  useEffect(() => {
    if (user) {
      setName(user.name || "");
      setEmail(user.email || "");
    }
    const savedSeed = localStorage.getItem("profileImageSeed");
    if (savedSeed) {
      setAvatarSeed(savedSeed);
    }
  }, [user]);

  const handleSave = (e: React.FormEvent) => {
    e.preventDefault();
    if (avatarSeed) {
      localStorage.setItem("profileImageSeed", avatarSeed);
      window.dispatchEvent(new Event("profileImageUpdated"));
    }
    // Form is not connected to a backend in this mock
    alert("Profile saved successfully!");
  };

  if (!user) return null;

  return (
    <div className="p-6 max-w-4xl mx-auto space-y-6">
      <PageHeader
        title="Edit Profile"
        description="Manage your account settings, contact information, and avatar preferences"
      />

      <form onSubmit={handleSave} className="space-y-6">
        <div className="p-6 bg-card border border-border rounded-xl shadow-sm space-y-4">
          <h2 className="text-lg font-semibold text-foreground">Basic Information</h2>
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">Full Name</label>
              <input 
                type="text" 
                value={name}
                onChange={(e) => setName(e.target.value)}
                className="w-full px-3 py-2 border border-border rounded-md bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">Role / Account Type</label>
              <input 
                type="text" 
                value={user.role === 'msme' ? 'MSME Owner' : 'Individual'}
                disabled
                className="w-full px-3 py-2 border border-border/50 rounded-md bg-muted text-muted-foreground cursor-not-allowed"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">Email Address</label>
              <input 
                type="email" 
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                placeholder="you@example.com"
                className="w-full px-3 py-2 border border-border rounded-md bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
            <div>
              <label className="block text-sm font-medium text-foreground mb-1">Phone Number</label>
              <input 
                type="tel" 
                value={phone}
                onChange={(e) => setPhone(e.target.value)}
                placeholder="+91 "
                className="w-full px-3 py-2 border border-border rounded-md bg-background text-foreground focus:outline-none focus:ring-2 focus:ring-primary"
              />
            </div>
          </div>
        </div>

        <AvatarSelector 
          initialSeed={avatarSeed} 
          onSelect={(seed) => setAvatarSeed(seed)}
        />

        <div className="flex justify-end gap-3 pt-2">
          <Button type="button" variant="outline">Cancel</Button>
          <Button type="submit">Save Changes</Button>
        </div>
      </form>
    </div>
  );
}
