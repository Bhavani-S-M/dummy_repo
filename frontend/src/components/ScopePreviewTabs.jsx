import React from 'react';

/**
 * Component to render scope section previews
 */
const ScopePreviewTabs = ({ activeTab, parsedDraft }) => {
  if (!parsedDraft) {
    return (
      <div className="text-center text-gray-500 dark:text-gray-400 py-12">
        <p>No scope data available. Please finalize the scope first.</p>
      </div>
    );
  }

  // Debug: Log the structure
  console.log('ScopePreviewTabs - activeTab:', activeTab);
  console.log('ScopePreviewTabs - parsedDraft keys:', Object.keys(parsedDraft));
  console.log('ScopePreviewTabs - parsedDraft:', parsedDraft);

  // Helper to render table from array of objects or array of arrays
  const renderTable = (data, title = '') => {
    if (!Array.isArray(data) || data.length === 0) {
      return <div className="text-gray-500 italic">No data available</div>;
    }

    // Check if data is array of objects
    if (typeof data[0] === 'object' && !Array.isArray(data[0])) {
      const headers = Object.keys(data[0]);
      return (
        <div className="overflow-x-auto">
          {title && <h4 className="font-semibold text-gray-800 dark:text-gray-200 mb-2">{title}</h4>}
          <table className="min-w-full border border-gray-300 dark:border-gray-600">
            <thead className="bg-gray-100 dark:bg-gray-700">
              <tr>
                {headers.map((header, idx) => (
                  <th key={idx} className="px-4 py-2 text-left text-sm font-semibold text-gray-700 dark:text-gray-200 border-b border-gray-300 dark:border-gray-600">
                    {header.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {data.map((row, rowIdx) => (
                <tr key={rowIdx} className="hover:bg-gray-50 dark:hover:bg-gray-800">
                  {headers.map((header, colIdx) => (
                    <td key={colIdx} className="px-4 py-2 text-sm text-gray-600 dark:text-gray-400 border-b border-gray-200 dark:border-gray-700">
                      {typeof row[header] === 'object' ? JSON.stringify(row[header]) : String(row[header] || '-')}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }

    // If array of arrays, render as simple table
    if (Array.isArray(data[0])) {
      return (
        <div className="overflow-x-auto">
          {title && <h4 className="font-semibold text-gray-800 dark:text-gray-200 mb-2">{title}</h4>}
          <table className="min-w-full border border-gray-300 dark:border-gray-600">
            <tbody>
              {data.map((row, rowIdx) => (
                <tr key={rowIdx} className={rowIdx === 0 ? "bg-gray-100 dark:bg-gray-700" : "hover:bg-gray-50 dark:hover:bg-gray-800"}>
                  {row.map((cell, cellIdx) => (
                    <td key={cellIdx} className={`px-4 py-2 text-sm ${rowIdx === 0 ? 'font-semibold text-gray-700 dark:text-gray-200' : 'text-gray-600 dark:text-gray-400'} border-b border-gray-200 dark:border-gray-700`}>
                      {String(cell || '-')}
                    </td>
                  ))}
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      );
    }

    // Fallback: render as list
    return (
      <ul className="list-disc list-inside space-y-1 ml-4">
        {data.map((item, idx) => (
          <li key={idx} className="text-gray-600 dark:text-gray-400">
            {String(item)}
          </li>
        ))}
      </ul>
    );
  };

  const renderValue = (value, depth = 0) => {
    if (value === null || value === undefined || value === '') return null;

    // Prevent infinite recursion
    if (depth > 5) {
      return <span className="text-gray-500 italic">...</span>;
    }

    if (Array.isArray(value)) {
      if (value.length === 0) return <span className="text-gray-500 italic">None</span>;

      // Check if this looks like tabular data
      if (value.length > 0 && typeof value[0] === 'object') {
        return renderTable(value);
      }

      return (
        <ul className="list-disc list-inside space-y-1 ml-4">
          {value.map((item, idx) => (
            <li key={idx} className="text-gray-600 dark:text-gray-400">
              {typeof item === 'object' ? renderValue(item, depth + 1) : String(item)}
            </li>
          ))}
        </ul>
      );
    } else if (typeof value === 'object') {
      return (
        <div className="ml-4 mt-2 space-y-2">
          {Object.entries(value).map(([k, v]) => {
            if (v === null || v === undefined || v === '') return null;
            return (
              <div key={k} className="flex gap-2">
                <span className="font-medium text-gray-700 dark:text-gray-300 min-w-[150px]">
                  {k.replace(/_/g, ' ')}:
                </span>
                <div className="flex-1">{renderValue(v, depth + 1)}</div>
              </div>
            );
          })}
        </div>
      );
    } else {
      return <span className="text-gray-600 dark:text-gray-400">{String(value)}</span>;
    }
  };

  const renderSection = (data, isTableSection = false) => {
    if (!data || typeof data !== 'object') {
      return <div className="text-gray-500 italic">No data available</div>;
    }

    // If this is marked as a table section and data is an array, render as table
    if (isTableSection && Array.isArray(data)) {
      return renderTable(data);
    }

    // If data is an array of objects at top level, render as table
    if (Array.isArray(data) && data.length > 0 && typeof data[0] === 'object') {
      return renderTable(data);
    }

    return (
      <div className="space-y-6">
        {Object.entries(data).map(([key, value]) => {
          if (value === null || value === undefined || value === '') return null;

          return (
            <div key={key} className="border-b border-gray-200 dark:border-gray-700 pb-4 last:border-0">
              <h4 className="text-lg font-semibold text-gray-800 dark:text-gray-200 mb-3">
                {key.replace(/_/g, ' ').replace(/\b\w/g, l => l.toUpperCase())}
              </h4>
              <div className="ml-4">
                {renderValue(value)}
              </div>
            </div>
          );
        })}
      </div>
    );
  };

  const getSectionData = () => {
    // Try multiple field name variations (case-insensitive)
    const findField = (...names) => {
      for (const name of names) {
        // Try exact match
        if (parsedDraft[name]) return parsedDraft[name];

        // Try case-insensitive match
        const lowerName = name.toLowerCase();
        const foundKey = Object.keys(parsedDraft).find(k => k.toLowerCase() === lowerName);
        if (foundKey && parsedDraft[foundKey]) return parsedDraft[foundKey];
      }
      return null;
    };

    let sectionData = null;

    switch (activeTab) {
      case 'overview':
        sectionData = findField('overview', 'project_overview', 'Overview', 'Project Overview');
        break;
      case 'activities':
        sectionData = findField('activities', 'activities_breakdown', 'Activities Breakdown', 'Activities', 'activity_breakdown');
        break;
      case 'resourcing':
        sectionData = findField('resourcing', 'resourcing_plan', 'Resourcing Plan', 'Resourcing', 'resource_plan', 'resources');
        break;
      case 'architecture':
        sectionData = findField('architecture', 'architecture_diagram', 'Architecture', 'Architecture Diagram', 'Architecture diagram', 'arch_diagram');
        break;
      case 'costing':
        sectionData = findField('costing', 'cost_projection', 'Cost Projection', 'cost_breakdown', 'pricing', 'Costing', 'costs', 'budget');
        break;
      case 'summary':
        sectionData = findField('summary', 'project_summary', 'Summary', 'Summery', 'Project Summary', 'executive_summary');
        break;
      default:
        sectionData = null;
    }

    console.log('ScopePreviewTabs - sectionData for', activeTab, ':', sectionData);

    // If no section-specific data, check if parsedDraft itself might be the section
    if (!sectionData && activeTab === 'overview') {
      sectionData = parsedDraft;
    }

    return sectionData;
  };

  const sectionData = getSectionData();
  const isTableSection = activeTab === 'activities' || activeTab === 'resourcing';

  return (
    <div className="p-6 bg-white dark:bg-dark-card rounded-lg border border-gray-200 dark:border-gray-700 max-h-[600px] overflow-y-auto">
      {sectionData ? renderSection(sectionData, isTableSection) : (
        <div className="text-center text-gray-500 italic py-8">
          <p className="mb-2">This section has no data in the current scope</p>
          <p className="text-sm font-medium mb-2">Available fields in scope:</p>
          <div className="text-xs bg-gray-100 dark:bg-gray-800 p-3 rounded inline-block">
            {Object.keys(parsedDraft).map((key, idx) => (
              <div key={idx} className="text-left">• {key}</div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};

export default ScopePreviewTabs;
