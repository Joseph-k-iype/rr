import { useState } from 'react';

interface EditModalProps {
  title: string;
  fields: { key: string; label: string; value: string; type?: string }[];
  onSave: (values: Record<string, string>) => void;
  onClose: () => void;
}

export function EditModal({ title, fields, onSave, onClose }: EditModalProps) {
  const [values, setValues] = useState<Record<string, string>>(
    Object.fromEntries(fields.map(f => [f.key, f.value]))
  );

  const handleSave = () => {
    onSave(values);
    onClose();
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/30" onClick={onClose}>
      <div className="bg-white rounded-lg shadow-xl w-full max-w-md mx-4" onClick={e => e.stopPropagation()}>
        <div className="px-5 py-4 border-b border-gray-100">
          <h3 className="text-sm font-medium text-gray-900">{title}</h3>
        </div>
        <div className="px-5 py-4 space-y-3">
          {fields.map(field => (
            <div key={field.key}>
              <label className="block text-xs font-medium text-gray-600 mb-1">{field.label}</label>
              {field.type === 'textarea' ? (
                <textarea
                  value={values[field.key]}
                  onChange={e => setValues(prev => ({ ...prev, [field.key]: e.target.value }))}
                  className="w-full rounded border border-gray-300 px-3 py-1.5 text-sm"
                  rows={3}
                />
              ) : (
                <input
                  type={field.type || 'text'}
                  value={values[field.key]}
                  onChange={e => setValues(prev => ({ ...prev, [field.key]: e.target.value }))}
                  className="w-full rounded border border-gray-300 px-3 py-1.5 text-sm"
                />
              )}
            </div>
          ))}
        </div>
        <div className="px-5 py-3 border-t border-gray-100 flex justify-end gap-2">
          <button onClick={onClose} className="px-3 py-1.5 text-xs text-gray-600 border border-gray-200 rounded hover:bg-gray-50">
            Cancel
          </button>
          <button onClick={handleSave} className="px-3 py-1.5 text-xs text-white bg-gray-900 rounded hover:bg-gray-800">
            Save
          </button>
        </div>
      </div>
    </div>
  );
}
