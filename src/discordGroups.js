export function messageGroups(messages, visible = () => true, boundary) {
 const groups = [];
 let group;
 for (const message of messages) {
  if (!group || message.id === boundary || group.author.id !== message.author.id) {
   group = {id: message.id, author: message.author, messages: []};
   groups.push(group);
  }
  if (visible(message)) group.messages.push(message);
 }
 return groups.filter(group => group.messages.length);
}
