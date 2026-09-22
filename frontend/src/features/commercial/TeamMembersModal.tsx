import React, { useState } from "react";
import { X, Users, UserPlus, Trash2, Mail, CheckCircle2, AlertTriangle } from "lucide-react";
import { Organization, TeamMember, UserRole } from "../../shared/types";

interface TeamMembersModalProps {
  isOpen: boolean;
  onClose: () => void;
  organization: Organization;
  members: TeamMember[];
  onInviteMember: (email: string, role: UserRole) => void;
  onRemoveMember: (memberId: string) => void;
}

export const TeamMembersModal: React.FC<TeamMembersModalProps> = ({
  isOpen,
  onClose,
  organization,
  members,
  onInviteMember,
  onRemoveMember,
}) => {
  const [inviteEmail, setInviteEmail] = useState("");
  const [inviteRole, setInviteRole] = useState<UserRole>("MEMBER");
  const [isSuccess, setIsSuccess] = useState(false);

  if (!isOpen) return null;

  const seatsUsed = organization.active_seats_30d;
  const maxSeats = organization.max_seats;
  const isNearLimit = seatsUsed >= maxSeats;
  const percentUsed = Math.min(100, Math.round((seatsUsed / maxSeats) * 100));

  const handleInvite = (e: React.FormEvent) => {
    e.preventDefault();
    if (!inviteEmail.trim()) return;
    onInviteMember(inviteEmail.trim(), inviteRole);
    setInviteEmail("");
    setIsSuccess(true);
    setTimeout(() => setIsSuccess(false), 3000);
  };

  const getRoleBadge = (role: UserRole) => {
    switch (role) {
      case "OWNER":
        return "bg-purple-950/80 text-purple-300 border-purple-800";
      case "ADMIN":
        return "bg-indigo-950/80 text-indigo-300 border-indigo-800";
      case "MEMBER":
        return "bg-blue-950/80 text-blue-300 border-blue-800";
      case "VIEWER":
        return "bg-gray-800 text-gray-300 border-gray-700";
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 bg-black/70 backdrop-blur-sm animate-fadeIn">
      <div className="bg-gray-900 border border-gray-800 rounded-2xl w-full max-w-2xl overflow-hidden shadow-2xl flex flex-col max-h-[90vh]">
        {/* Header */}
        <div className="px-6 py-4 border-b border-gray-800 flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-lg bg-pink-500/20 text-pink-400 flex items-center justify-center">
              <Users className="w-4 h-4" />
            </div>
            <div>
              <h2 className="text-sm font-bold text-white">Team & Seat Management</h2>
              <p className="text-xs text-gray-400">{organization.name} &bull; {organization.plan} Plan</p>
            </div>
          </div>
          <button
            type="button"
            onClick={onClose}
            className="text-gray-400 hover:text-white transition p-1 rounded-lg hover:bg-gray-800"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Seat Usage Bar */}
        <div className="px-6 py-4 bg-gray-950/50 border-b border-gray-800/80">
          <div className="flex items-center justify-between mb-1.5 text-xs">
            <span className="text-gray-300 font-medium">Active Seats Allocated</span>
            <span className="font-mono text-gray-200">
              <strong className="text-white">{seatsUsed}</strong> / {maxSeats} seats ({percentUsed}%)
            </span>
          </div>
          <div className="w-full h-2 bg-gray-800 rounded-full overflow-hidden">
            <div
              className={`h-full rounded-full transition-all duration-500 ${
                isNearLimit ? "bg-amber-500" : "bg-gradient-to-r from-pink-500 to-indigo-500"
              }`}
              style={{ width: `${percentUsed}%` }}
            />
          </div>
          {isNearLimit && (
            <div className="mt-2.5 flex items-center gap-1.5 text-[11px] text-amber-400 bg-amber-950/30 border border-amber-800/50 px-2.5 py-1.5 rounded-lg">
              <AlertTriangle className="w-3.5 h-3.5 flex-shrink-0" />
              <span>Seat quota limit reached. Additional active contributors will be soft-gated.</span>
            </div>
          )}
        </div>

        {/* Invite Member Section */}
        <div className="p-6 border-b border-gray-800">
          <h3 className="text-xs font-semibold text-gray-300 mb-3 flex items-center gap-1.5">
            <UserPlus className="w-3.5 h-3.5 text-pink-400" />
            <span>Invite Colleague or Contributor</span>
          </h3>
          <form onSubmit={handleInvite} className="flex gap-2">
            <div className="relative flex-grow">
              <Mail className="w-4 h-4 text-gray-500 absolute left-3 top-2.5" />
              <input
                type="email"
                required
                value={inviteEmail}
                onChange={(e) => setInviteEmail(e.target.value)}
                placeholder="colleague@company.com"
                className="w-full bg-gray-950 border border-gray-800 rounded-xl pl-9 pr-3 py-2 text-xs text-white placeholder-gray-500 focus:outline-none focus:border-pink-500"
              />
            </div>
            <select
              value={inviteRole}
              onChange={(e) => setInviteRole(e.target.value as UserRole)}
              className="bg-gray-950 border border-gray-800 rounded-xl px-3 py-2 text-xs text-gray-200 focus:outline-none focus:border-pink-500"
            >
              <option value="MEMBER">Member</option>
              <option value="ADMIN">Admin</option>
              <option value="VIEWER">Viewer</option>
            </select>
            <button
              type="submit"
              className="px-4 py-2 bg-gradient-to-r from-pink-500 to-indigo-500 hover:from-pink-600 hover:to-indigo-600 text-white rounded-xl text-xs font-semibold transition flex items-center gap-1.5 shadow"
            >
              <UserPlus className="w-3.5 h-3.5" />
              <span>Invite</span>
            </button>
          </form>

          {isSuccess && (
            <div className="mt-2 text-xs text-emerald-400 flex items-center gap-1.5">
              <CheckCircle2 className="w-3.5 h-3.5" />
              <span>Invitation dispatched successfully!</span>
            </div>
          )}
        </div>

        {/* Members List */}
        <div className="p-6 overflow-y-auto flex-grow divide-y divide-gray-800/60">
          <h3 className="text-xs font-semibold text-gray-400 uppercase tracking-wider mb-3">
            Active Organization Members ({members.length})
          </h3>
          <div className="space-y-1">
            {members.map((member) => (
              <div
                key={member.id}
                className="flex items-center justify-between py-2.5 px-2 rounded-lg hover:bg-gray-800/40 transition"
              >
                <div className="flex items-center gap-3">
                  <div className="w-8 h-8 rounded-full bg-gray-800 border border-gray-700 flex items-center justify-center font-bold text-xs text-white">
                    {member.full_name ? member.full_name.charAt(0) : member.username.charAt(0).toUpperCase()}
                  </div>
                  <div>
                    <div className="flex items-center gap-2">
                      <span className="text-xs font-medium text-white">
                        {member.full_name || member.username}
                      </span>
                      <span
                        className={`text-[9px] font-mono px-1.5 py-0.2 rounded border ${getRoleBadge(
                          member.role
                        )}`}
                      >
                        {member.role}
                      </span>
                    </div>
                    <span className="text-[11px] text-gray-400">{member.email}</span>
                  </div>
                </div>

                {member.role !== "OWNER" && (
                  <button
                    type="button"
                    onClick={() => onRemoveMember(member.id)}
                    className="p-1.5 text-gray-500 hover:text-red-400 hover:bg-red-950/20 rounded-lg transition"
                    title="Remove member"
                  >
                    <Trash2 className="w-4 h-4" />
                  </button>
                )}
              </div>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
};
