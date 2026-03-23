import {
  DndContext,
  closestCenter,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
} from "@dnd-kit/core";
import {
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from "@dnd-kit/sortable";
import { CSS } from "@dnd-kit/utilities";
import { useReorderWatchlist } from "../hooks/useWatchlist";
import WatchlistRow from "./WatchlistRow";

function SortableRow({ item }) {
  const {
    attributes,
    listeners,
    setNodeRef,
    transform,
    transition,
    isDragging,
  } = useSortable({ id: item.id });

  const style = {
    transform: CSS.Transform.toString(transform),
    transition,
    opacity: isDragging ? 0.5 : 1,
  };

  return (
    <tbody ref={setNodeRef} style={style}>
      <WatchlistRow
        item={item}
        dragHandleProps={{ ...attributes, ...listeners }}
      />
    </tbody>
  );
}

export default function WatchlistTable({ items }) {
  const reorder = useReorderWatchlist();

  const sensors = useSensors(
    useSensor(PointerSensor),
    useSensor(KeyboardSensor, {
      coordinateGetter: sortableKeyboardCoordinates,
    })
  );

  const handleDragEnd = (event) => {
    const { active, over } = event;
    if (!over || active.id === over.id) return;

    const oldIndex = items.findIndex((item) => item.id === active.id);
    const newIndex = items.findIndex((item) => item.id === over.id);

    const newOrder = [...items];
    const [removed] = newOrder.splice(oldIndex, 1);
    newOrder.splice(newIndex, 0, removed);

    reorder.mutate(newOrder.map((item) => item.id));
  };

  if (items.length === 0) {
    return (
      <div className="text-center py-16 text-mid-brown font-sans">
        <p className="text-lg mb-2">No items in watchlist</p>
        <p className="text-sm text-light-brown">Add a ticker to get started.</p>
      </div>
    );
  }

  return (
    <DndContext
      sensors={sensors}
      collisionDetection={closestCenter}
      onDragEnd={handleDragEnd}
    >
      <table className="w-full">
        <thead>
          <tr className="text-left text-xs text-mid-brown uppercase tracking-wide border-b-2 border-ink">
            <th className="py-3 px-4 w-8"></th>
            <th className="py-3 px-4">Ticker</th>
            <th className="py-3 px-4">Status</th>
            <th className="py-3 px-4">Entry</th>
            <th className="py-3 px-4">Tags</th>
            <th className="py-3 px-4 w-8"></th>
          </tr>
        </thead>
        <SortableContext
          items={items.map((item) => item.id)}
          strategy={verticalListSortingStrategy}
        >
          {items.map((item) => (
            <SortableRow key={item.id} item={item} />
          ))}
        </SortableContext>
      </table>
    </DndContext>
  );
}
