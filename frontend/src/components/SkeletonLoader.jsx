import React from 'react';

// Reusable skeleton components
export const SkeletonCard = () => (
  <div className="bg-white overflow-hidden shadow rounded-xl animate-pulse">
    <div className="p-5">
      <div className="flex items-center">
        <div className="flex-shrink-0">
          <div className="w-8 h-8 bg-gray-300 rounded-md"></div>
        </div>
        <div className="ml-5 w-0 flex-1">
          <div className="h-4 bg-gray-300 rounded w-24 mb-2"></div>
          <div className="h-8 bg-gray-300 rounded w-16"></div>
        </div>
      </div>
    </div>
  </div>
);

export const SkeletonTableRow = () => (
  <tr className="animate-pulse">
    <td className="px-6 py-4 whitespace-nowrap">
      <div className="h-4 bg-gray-300 rounded w-12"></div>
    </td>
    <td className="px-6 py-4 whitespace-nowrap">
      <div className="h-4 bg-gray-300 rounded w-32"></div>
    </td>
    <td className="px-6 py-4 whitespace-nowrap">
      <div className="h-4 bg-gray-300 rounded w-24"></div>
    </td>
    <td className="px-6 py-4 whitespace-nowrap">
      <div className="h-6 bg-gray-300 rounded-full w-16"></div>
    </td>
    <td className="px-6 py-4 whitespace-nowrap">
      <div className="h-6 bg-gray-300 rounded-full w-20"></div>
    </td>
    <td className="px-6 py-4 whitespace-nowrap">
      <div className="h-4 bg-gray-300 rounded w-12"></div>
    </td>
  </tr>
);

export const SkeletonLeaderboardRow = () => (
  <tr className="animate-pulse bg-white border border-gray-200">
    <td className="px-6 py-5 whitespace-nowrap">
      <div className="flex items-center">
        <div className="w-8 h-8 bg-gray-300 rounded-full"></div>
        <div className="ml-3 h-6 bg-gray-300 rounded w-8"></div>
      </div>
    </td>
    <td className="px-6 py-5 whitespace-nowrap">
      <div className="flex items-center">
        <div className="h-12 w-12 bg-gray-300 rounded-full"></div>
        <div className="ml-4">
          <div className="h-5 bg-gray-300 rounded w-32 mb-2"></div>
          <div className="h-4 bg-gray-300 rounded w-24"></div>
        </div>
      </div>
    </td>
    <td className="px-6 py-5 whitespace-nowrap text-center">
      <div className="h-6 bg-gray-300 rounded-full w-16 mx-auto"></div>
    </td>
    <td className="px-6 py-5 whitespace-nowrap text-center">
      <div className="h-8 bg-gray-300 rounded-full w-20 mx-auto"></div>
    </td>
  </tr>
);

export const SkeletonStatsCard = () => (
  <div className="bg-gradient-to-br from-gray-200 to-gray-300 shadow-lg rounded-xl p-6 animate-pulse">
    <div className="flex items-center justify-between">
      <div className="flex-1">
        <div className="h-4 bg-gray-400 rounded w-24 mb-3"></div>
        <div className="h-10 bg-gray-400 rounded w-20"></div>
      </div>
      <div className="w-12 h-12 bg-gray-400 rounded-full"></div>
    </div>
  </div>
);

export const SkeletonCallDetailCard = () => (
  <div className="bg-white shadow rounded-xl p-6 animate-pulse">
    <div className="space-y-4">
      <div className="h-6 bg-gray-300 rounded w-3/4"></div>
      <div className="h-4 bg-gray-300 rounded w-full"></div>
      <div className="h-4 bg-gray-300 rounded w-5/6"></div>
      <div className="h-4 bg-gray-300 rounded w-4/6"></div>
    </div>
  </div>
);

export const SkeletonText = ({ lines = 3, className = "" }) => (
  <div className={`space-y-2 ${className} animate-pulse`}>
    {Array.from({ length: lines }).map((_, i) => (
      <div
        key={i}
        className={`h-4 bg-gray-300 rounded ${
          i === lines - 1 ? 'w-5/6' : 'w-full'
        }`}
      ></div>
    ))}
  </div>
);

export const SkeletonButton = () => (
  <div className="h-10 bg-gray-300 rounded-md w-32 animate-pulse"></div>
);

