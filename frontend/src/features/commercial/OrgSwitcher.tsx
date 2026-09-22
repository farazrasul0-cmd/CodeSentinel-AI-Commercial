import React, { useState } from "react";
import { ChevronDown, Check, Plus } from "lucide-react";
import { Organization } from "../../shared/types";

interface OrgSwitcherProps {
  organizations: Organization[];
  currentOrg: Organization;
  onSelectOrg: (org: Organization) => void;
  onCreateOrg?: () => void;
}

export const OrgSwitcher: React.FC<OrgSwitcherProps> = ({
  organizations,
  currentOrg,
  onSelectOrg,
  onCreateOrg,
}) => {
  const [isOpen, setIsOpen] = useState(false);

  const getPlanBadge = (plan: string) => {
    switch (plan) {
      case "ENTERPRISE":
        return "bg-purple-900/60 text-purple-300 border-purple-700/50";
      case "TEAM":
        return "bg-blue-900/60 text-blue-300 border-blue-700/50";
      default:
        return "bg-gray-800 text-gray-300 border-gray-700";
    }
  };

  return (
    <div className="relative">
      <button
        type="button"
        onClick={() => setIsOpen(!isOpen)}
        className="flex items-center gap-2.5 px-3 py-1.5 rounded-lg bg-gray-900/90 hover:bg-gray-800 border border-gray-800 transition text-left text-xs font-medium text-gray-200"
      >
        <div className="w-5 h-5 rounded bg-gradient-to-br from-indigo-500 to-purple-600 flex items-center justify-center text-white text-[10px] font-bold">
          {currentOrg.name.charAt(0)}
        </div>
        <div className="flex flex-col">
          <div className="flex items-center gap-1.5">
            <span className="font-semibold text-gray-100 max-w-[130px] truncate">
              {currentOrg.name}
            </span>
            <span
              className={`text-[9px] font-mono px-1 py-0.2 rounded border ${getPlanBadge(
                currentOrg.plan
              )}`}
            >
              {currentOrg.plan}
            </span>
          </div>
        </div>
        <ChevronDown className="w-3.5 h-3.5 text-gray-400 ml-1" />
      </button>

      {isOpen && (
        <>
          <div
            className="fixed inset-0 z-40"
            onClick={() => setIsOpen(false)}
          />
          <div className="absolute left-0 mt-2 w-64 bg-gray-900 border border-gray-800 rounded-xl shadow-2xl py-2 z-50 text-xs">
            <div className="px-3 py-1 text-[10px] font-semibold text-gray-400 uppercase tracking-wider">
              Organizations
            </div>
            <div className="divide-y divide-gray-800/60 max-h-56 overflow-y-auto">
              {organizations.map((org) => {
                const isSelected = org.id === currentOrg.id;
                return (
                  <button
                    key={org.id}
                    type="button"
                    onClick={() => {
                      onSelectOrg(org);
                      setIsOpen(false);
                    }}
                    className={`w-full flex items-center justify-between px-3 py-2 text-left hover:bg-gray-800/70 transition ${
                      isSelected ? "bg-white/5" : ""
                    }`}
                  >
                    <div className="flex items-center gap-2">
                      <div className="w-5 h-5 rounded bg-gray-800 border border-gray-700 flex items-center justify-center text-gray-300 font-bold text-[10px]">
                        {org.name.charAt(0)}
                      </div>
                      <div className="flex flex-col">
                        <span className="font-medium text-gray-200 truncate max-w-[140px]">
                          {org.name}
                        </span>
                        <span className="text-[10px] text-gray-400">
                          {org.active_seats_30d} / {org.max_seats} seats used
                        </span>
                      </div>
                    </div>
                    {isSelected && <Check className="w-3.5 h-3.5 text-pink-400" />}
                  </button>
                );
              })}
            </div>

            <div className="border-t border-gray-800 pt-1 mt-1">
              <button
                type="button"
                onClick={() => {
                  setIsOpen(false);
                  if (onCreateOrg) onCreateOrg();
                }}
                className="w-full flex items-center gap-2 px-3 py-2 text-pink-400 hover:text-pink-300 hover:bg-gray-800/50 transition font-medium"
              >
                <Plus className="w-3.5 h-3.5" />
                <span>Create New Organization</span>
              </button>
            </div>
          </div>
        </>
      )}
    </div>
  );
};
