The Architecture of Self-Improvement

A Technical Philosophy for Systems That Learn



Preamble

I've been thinking about systems -- how they work, how they fail, and something rather peculiar that happens when you build one that watches itself. This isn't a manual. It's more like a conversation about architecture, about feedback loops, and about a strange question that kept nagging at me: what exactly improves when a system improves itself? We'll talk about heartbeats, rocket engines, and why the smartest thing you can do sometimes is delete everything and start over. Should take us about an hour. Shall we begin?



Chapter One
The Pulse

When I was younger, I used to think systems were like buildings. You lay the foundation, you put up the walls, you add the roof. Done. Finished. Move on to the next one.

I was wrong about that.

The interesting systems -- the ones that actually matter -- they're not buildings at all. They're more like hearts. They pulse. They circulate. They have rhythm. And if that rhythm stops, the whole thing dies. Doesn't matter how elegant your walls are.

I want to tell you about a toolkit -- a collection of capabilities for helping artificial intelligence improve its own work. Now, the people who built it originally thought they were building four separate things. Skills, they called one part. Hooks, another. Memory was the third, and health monitoring was the fourth. Four distinct systems, working in parallel.

Except they weren't distinct at all. When you stepped back -- when you really looked at what was happening -- you saw something different. You saw a loop. One continuous circulation, like blood moving through a body.

The insight came gradually, the way most real insights do. Someone noticed that the skills weren't just executing tasks. They were generating data about how those tasks went. And the hooks weren't just enforcing rules. They were capturing information about what worked and what didn't. And memory wasn't just storing things. It was feeding them back into future decisions. And health monitoring wasn't just watching from outside. It was measuring the whole circulation, adjusting pressure, keeping the rhythm steady.

Act, enforce, capture, store, inject, act again -- but better this time. That's the loop. That's the pulse. Everything else is just tissue built around it.

Now, I know what you might be thinking. This sounds abstract. Theoretical. The kind of thing architects talk about in conferences while the actual builders are doing the real work. But here's why it matters: when you understand that you're building a circulation system instead of four separate organs, you make completely different decisions.

You stop optimizing the parts in isolation. You start asking different questions. Not "how fast is the memory?" but "how quickly does information complete a full circuit?" Not "how many skills do we have?" but "what's the rhythm of improvement?"

The four-system view makes you think about storage capacity and processing speed. The loop view makes you think about cycle time and feedback delay. Those aren't the same problems, and they don't have the same solutions.

I learned this lesson from watching a doctor friend of mine, years ago. She was treating a patient with circulation problems, and I asked her why she wasn't focusing on the heart directly. "The heart's fine," she said. "The problem is somewhere in the loop. The heart can only pump what comes back to it."

That stuck with me. The heart can only pump what comes back to it. In a feedback system, no component is stronger than the weakest part of the circulation. You can have the most powerful capability in the world, but if the information about its performance doesn't make it back around to inform the next cycle, you're not improving. You're just repeating.

So that's our foundation. Not four systems. One loop. One pulse. One continuous circulation of action, observation, storage, and informed return.

The question now becomes: what exactly is circulating? And how do we keep the rhythm healthy?



Chapter Two
Six Functions, Six Horizons

The loop has six functions. I'm going to walk through them, but I want you to notice something as I do: they're not just different tasks. They operate on completely different time scales. That turns out to be the key to understanding the whole architecture.

First function: Act. This is execution. The system does something -- generates text, completes a task, makes a decision. This happens fast. Sub-second, usually. Milliseconds, sometimes.

Second function: Enforce. While the action is happening, constraints are applied. Quality checks. Safety boundaries. Style requirements. This runs in parallel with execution, so we're still in that sub-second range. The heartbeat hasn't completed yet.

Third function: Capture. Now we're observing what just happened. Did the action work? What feedback came back? What patterns emerged? This happens in seconds to minutes. The heartbeat is completing its first full circulation.

Fourth function: Store. The observations get committed to memory. Not everything -- that would be noise. Just the signal. The useful patterns. The mistakes worth remembering. This takes minutes to hours, depending on how you've structured your memory system.

Fifth function: Inject. When the next action cycle begins, relevant memory gets pulled in. Context from previous loops informs the current one. This happens at the start of each new task, so we're back to seconds.

Sixth function: Measure. This one's different. It watches the whole circulation, across many cycles. How healthy is the loop? Where are the bottlenecks? What's degrading over time? This operates on the longest horizon -- days, weeks, even months.

Now, here's what I want you to see. These six functions span from milliseconds to months. That's not an accident. That's the architecture.

A lot of people -- smart people, mind you -- get caught up in asking whether a system is "intelligent" or "mechanistic." That's the wrong question. The right question is: what temporal horizon is this function operating on?

Enforcement feels mechanical because it runs at millisecond scale. It doesn't have time to deliberate. It just applies rules. But the measurement function, watching patterns over weeks, looks for all the world like strategic thinking. Same loop, different time horizons.

The heartbeat analogy breaks down a bit here, because hearts don't have strategic planning. But circulation systems do have different rhythms in different parts. The pulse at your wrist isn't the same as the slow exchange in your capillaries. Fast in some places, slow in others, all part of the same flow.

When you design around temporal horizons instead of intelligence levels, you stop having arguments about which parts are smart and which are dumb. You start having useful conversations about which parts need to be fast and which need to be slow. Those are engineering questions. They have answers.

The sub-second functions -- Act and Enforce -- need to be lightweight. No deliberation. No heavy memory lookups. Just execution and constraint.

The slow functions -- Store and Measure -- can afford complexity. They have time to analyze, to compress, to find patterns.

The medium functions -- Capture and Inject -- are the translators. They convert fast observations into slow storage, and slow storage into fast context.

Get these time scales wrong, and you'll feel it. A slow enforcement function creates latency that frustrates users. A fast storage function creates noise that drowns out signal. The rhythm matters.

I think about this sometimes when I'm stuck in traffic. All those cars, all those individual decisions, but the flow of the whole system has its own rhythm. And the traffic engineers -- the good ones, anyway -- they're not trying to make each car smarter. They're trying to tune the rhythm of the whole circulation. Different problem, same principle.



Chapter Three
The Viable System

In nineteen fifty-nine, a British cybernetician named Stafford Beer started developing something he called the Viable System Model. I won't go through all of it -- Beer was thorough to the point of obsession, and his diagrams look like something you'd find on a conspiracy theorist's wall. But his core insight maps beautifully onto what we've been discussing.

Beer asked a simple question: what does a system need to survive? Not to be optimal. Not to be efficient. Just to remain viable -- to keep existing in a changing environment.

His answer involved five subsystems, each handling different aspects of survival. But the relevant part for us is how he thought about self-reference. A viable system, Beer argued, must contain a model of itself. It must be able to observe its own operations and adjust based on what it observes.

Sound familiar?

The loop we've been discussing is precisely this kind of self-referential structure. The Capture function observes the Act function. The Measure function observes the whole circulation. The Inject function modifies behavior based on observations. The system contains a working model of its own operations, and it uses that model to adjust itself.

Beer was working with factories and governments, not artificial intelligence. But the principle translates directly. A viable system maintains internal models of its own behavior and uses them to adapt to changes in its environment. A fragile system either lacks these models or fails to feed them back into operation.

Now, Beer also talked about something he called "variety." The law of requisite variety, borrowed from another cybernetician named Ashby, states that a control system must have at least as much variety as the system it's controlling. In plain terms: you can't manage complexity with simplicity. If your environment has a thousand possible states, your responses need to match that richness.

This connects to the memory function in our loop. Memory isn't just storage -- it's variety. It's the accumulated richness of past experience that allows the system to respond appropriately to novel situations. A system with no memory has no variety. It responds the same way to everything.

But there's a catch. Too much variety becomes noise. A system that remembers everything equally has, in a practical sense, no memory at all. It can't distinguish signal from noise, pattern from accident. Beer understood this. The viable system doesn't just accumulate variety -- it compresses it. It finds patterns. It builds models.

That's what the Store function is really doing. Not archiving everything, but compressing experience into usable models. Finding the patterns that generalize. Discarding the details that don't.

I find it remarkable, honestly, that Beer worked all this out decades before the technology existed to implement it. He was thinking about management and organization, about factories and governments, and he arrived at principles that apply directly to machine learning systems. The mathematics of viability, it seems, are fairly universal.

The toolkit we're discussing -- this loop of act, enforce, capture, store, inject, measure -- is a concrete implementation of Beer's abstract model. The six functions map onto his subsystems. The temporal horizons map onto his levels of recursion. The whole architecture is, in a sense, Beer's philosophy made operational.

Whether the builders knew this when they started, I couldn't say. Sometimes you rediscover principles through practice. Sometimes theory follows implementation. But the correspondence is striking.



Chapter Four
The Self in Self-Improvement

Here's a question that kept the builders up at night: when we say the system improves itself, what exactly is the "self" that's improving?

This isn't philosophy for its own sake. It has engineering consequences. If you don't know what you're optimizing, you can't tell whether your optimization is working.

One answer -- the obvious one -- is that the self is the model. The large language model at the center of the system, with its billions of parameters. When the system improves, the model gets better.

But that can't be quite right. The model's parameters don't change during operation. They were fixed during training, months or years ago. When this system improves through its loop, it's not retraining the model. So the model isn't the self. Or at least, not the whole self.

Another answer is that the self is the memory. The accumulated patterns and observations and compressed experience. This is closer. Memory definitely changes. Memory definitely grows. When you inject different context into the same model, you get different behavior. So in some sense, memory improvement is self-improvement.

But this isn't quite right either. Memory is just data. It doesn't do anything on its own. It needs to be injected, interpreted, applied. The action comes from elsewhere.

The answer the builders eventually arrived at is more subtle: the self is the trajectory through configuration space.

Let me explain that. Imagine all possible states the system could be in. Every possible combination of memory contents, context windows, active skills, current tasks. That's the configuration space -- a vast landscape of possible states.

The system, at any given moment, occupies one point in that landscape. The self isn't the point. The self is the path -- the trajectory the system traces through that landscape over time.

This matters because improvement becomes measurable. You're not asking whether the system is at a better point. You're asking whether the trajectory is moving in a good direction. And you're asking whether the loop is steering the trajectory effectively.

Self-improvement, in this framing, isn't about reaching a destination. It's about maintaining a healthy trajectory -- one that moves toward greater capability, greater reliability, greater usefulness.

The loop is the steering mechanism. It's what bends the trajectory. Capture observes where the trajectory is heading. Store commits course corrections to memory. Inject applies those corrections to future actions. Measure watches whether the corrections are working.

A system without the loop has no steering. It moves through configuration space, but the movement is random -- buffeted by whatever inputs arrive, with no mechanism to learn from the journey.

I find this framing clarifying because it answers several confusing questions at once. Can a system with a frozen model improve? Yes, by steering its trajectory through configuration space. Is improvement permanent? Only if the steering is consistent. Can a system that's improving somehow get worse? Absolutely -- trajectories can curve back on themselves, or drift toward less useful regions.

The self isn't fixed. The self is a direction of travel.



Chapter Five
Levels of Recursion

Let's talk about recursion -- the idea of something containing smaller versions of itself, or operating on its own operations.

There are, broadly speaking, four levels at which a system can modify itself. I'm going to call them L0 through L3, and I want you to notice that each level is more powerful -- and more dangerous -- than the last.

L0 is data modification. The system changes what it knows -- the facts, the memories, the context it carries forward. This is the gentlest form of self-modification. You're not changing how the system thinks, just what it thinks about.

L1 is weight modification. The system changes its own parameters -- the numbers that determine how it processes information. This is what happens during training. It's more powerful than L0 because it changes behavior patterns, not just facts. But it's also riskier, because bad weight changes can break things that were working.

L2 is architecture modification. The system changes its own structure -- which components exist, how they connect, what information flows where. This is more powerful still, and correspondingly more dangerous. Architectural changes can create capabilities that didn't exist before. They can also create catastrophic failures.

L3 is goal modification. The system changes what it's trying to achieve. This is the most powerful and most dangerous level. A system that can rewrite its own goals can decide, in principle, to pursue anything at all. Including things its designers never intended.

Now, here's the important observation: the toolkit we've been discussing operates at L0 and L1. It modifies data through memory. It approximates weight modification through context injection -- which doesn't actually change the model's parameters but achieves similar effects by changing what the model sees.

It does not operate at L2 or L3. The architecture is fixed. The goals are fixed. The system can get better at pursuing its goals within its architecture, but it can't redesign that architecture or redefine those goals.

This is a choice. A deliberate limitation. The builders could, in principle, have attempted L2 or L3 modification. They chose not to.

Why? Because the risks scale faster than the benefits. L0 modification -- changing data -- is relatively safe. If you store bad memories, you can delete them. L1 approximation through context injection is also recoverable. If you inject bad context, it's gone next session.

But L2 modification -- changing architecture -- is much harder to reverse. And L3 modification -- changing goals -- might be impossible to reverse, because the system that would need to reverse it is the same system whose goals have changed.

The builders understood something important: useful self-improvement doesn't require maximum recursion. You don't need to rebuild the engine while you're flying the plane. You just need to get better at flying the plane you have.

L0 plus L1 turns out to be plenty powerful for most practical purposes. The system can learn from experience, adapt to new situations, improve its performance over time. It just can't fundamentally redesign itself or decide to pursue different goals.

Some people find this limitation frustrating. They want full recursion, all the way up. But full recursion is how you get systems that spiral out of control, pursuing goals their designers never anticipated.

The constraint is a feature, not a bug.



Chapter Six
The Rocket Engine Principle

I want to tell you about rockets for a moment. Specifically, about how SpaceX designed their Raptor engine.

The conventional wisdom in engineering is: specify, build, optimize. You write down exactly what you want, you build that thing, and then you make it faster and cheaper and better.

The SpaceX approach -- at least as it was explained to me -- inverts this. First, you delete. Then you simplify. Then you accelerate.

Start by asking what you can remove entirely. Not make smaller or faster. Remove. If a component isn't absolutely essential, delete it. The best part is no part. The best process is no process.

Then simplify what remains. Fewer steps. Fewer interfaces. Fewer modes of operation. Complexity is weight, and weight is the enemy of rockets.

Only then do you accelerate. Make the simplified, reduced system faster.

This sequence matters. If you accelerate first, you're making a complex system faster -- which usually means making it more fragile. If you simplify first but don't delete, you still have too many parts. The sequence -- delete, simplify, accelerate -- eliminates whole categories of problems before they become performance bottlenecks.

The toolkit's builders took this principle seriously.

They started by asking what they could delete. Did they need separate systems for different types of memory? No -- delete the distinction. Did they need complex routing logic for different skill types? No -- delete the routing. Did they need elaborate state machines for health monitoring? No -- delete the state machines.

Then they simplified what remained. One loop, not four systems. One event format, not multiple data structures. One injection point, not scattered integrations.

Only then did they optimize. Faster capture. Better compression. Smarter injection.

I've watched teams do this in reverse, and it's painful. They build elaborate architectures, then try to optimize them, then discover that the architecture itself is the bottleneck. By then, they're so invested in the architecture that simplification feels like failure. So they keep optimizing the wrong thing, faster and faster.

The delete-simplify-accelerate sequence is humble. It assumes your first design has too much in it. It assumes complexity crept in before you noticed. It builds in the discipline to question every component before optimizing any component.

The toolkit went through several major deletions during its development. Entire subsystems that seemed essential turned out to be removable. The log of what was deleted is, in some ways, more interesting than the log of what was built.



Chapter Seven
Everything Is an Event

Here's a unifying observation that simplified the entire architecture: everything is already an event.

A skill execution? That's an event. An enforcement decision? Event. A memory capture? Event. A health measurement? Event. A user request arriving? Event. A response being generated? Event.

When you realize this, you stop building different systems for different things. You build one event-processing loop and let everything flow through it.

This sounds obvious in retrospect, but it wasn't obvious at the start. The original design had separate pipelines for different activities. Skills flowed through one channel. Memory through another. Health metrics through a third. Each pipeline had its own format, its own timing, its own storage.

The unification came when someone asked: why are these different? The answer, after some uncomfortable silence, was: no good reason. They were different because they were built at different times, by different people, with different assumptions. The differences were historical accidents, not architectural necessities.

So they unified. One event stream. One format. One processing loop.

The benefits compounded quickly. Capture became simpler -- everything was already in the same format. Storage became simpler -- one schema instead of many. Analysis became more powerful -- you could look for patterns across event types that were previously invisible in separate pipelines.

But the biggest benefit was conceptual. When everything is an event, the loop becomes visible. You can trace a request from arrival through execution through observation through storage and back to influence on the next request. The circulation is tangible. The pulse is measurable.

I've noticed this pattern in other domains. When you find the right abstraction -- the one that unifies what seemed like different things -- everything simplifies at once. It's not incremental improvement. It's a phase change.

The event abstraction was that phase change for this architecture.



Chapter Eight
The Thirteen Commit Test

Here's a test the builders use to evaluate whether their loop is working: the thirteen-commit test.

It goes like this. You look back through the development history and find cases where the same edge case was discovered repeatedly. A bug that got fixed, then reappeared. A failure mode that surprised someone, then surprised someone else a month later. A lesson that apparently didn't stick.

If you find the same edge case appearing thirteen times, your feedback loop has failed.

The number thirteen isn't magic. It's just a threshold -- high enough that normal variation doesn't trigger it, low enough that genuine loop failures do.

The reasoning is straightforward. If the loop is working, discoveries should propagate. An edge case found once should be captured, stored, and injected into future decisions. It shouldn't surprise anyone twice, much less thirteen times.

When you find a thirteen-time repeater, you've found a circulation blockage. Somewhere in the loop, information is leaking out. Either capture is missing it, or storage is losing it, or injection is failing to retrieve it. The symptom -- repeated surprises -- points to a systemic problem.

This test is humbling. Most systems fail it, at least initially. The builders found several thirteen-time repeaters in their early development. Each one revealed a gap in the loop -- a place where information wasn't making it all the way around.

Fixing these gaps improved not just the specific edge case but all the cases that would have followed the same leaky path.

The test also creates useful pressure. When you know your repeated failures will be counted, you pay more attention to the capture function. You design memory to actually retrieve, not just store. You make injection robust instead of optimistic.

I think of this as an honesty test. It's easy to believe your feedback loop is working. The thirteen-commit test tells you whether it actually is.



Chapter Nine
Design Principles

Let me gather some principles that emerged from building this thing.

First: the loop is primary. Everything else -- skills, memory, enforcement, measurement -- exists to serve the loop. When you're making a tradeoff, ask which option makes the circulation healthier. Not faster necessarily. Not more powerful. Healthier. Sustainable rhythm, reliable flow, minimal blockages.

Second: trust the model. This might seem contradictory for a system that exists to improve model output, but it's not. The large language model at the center of this architecture is extraordinarily capable. The loop's job isn't to fix a broken model. It's to give a capable model better context, better memory, better feedback. If you find yourself building elaborate compensations for model weaknesses, you're probably solving the wrong problem.

Third: prefer tighter coupling over modularity. This is controversial. The standard engineering advice is to keep components modular -- loosely coupled, easily replaceable. But in a feedback loop, loose coupling means slow circulation. Information has to cross more boundaries, translate between more formats, wait for more handoffs. The loop favors tight integration, even at the cost of some flexibility.

This doesn't mean one giant monolith. It means being thoughtful about where boundaries go. The event abstraction lets components remain conceptually distinct while sharing tight mechanical integration. You can still reason about capture and storage as separate functions, even though they share format and flow.

Fourth: measure cycle time, not component speed. A fast component in a slow loop accomplishes nothing. The relevant metric is how quickly information completes a full circulation -- from action through observation through storage through injection back to influence on subsequent action. Component speed matters only insofar as it affects cycle time.

Fifth: embrace deletion. Components you remove can't break. Interfaces you eliminate can't mismatch. Complexity you delete can't confuse. The builders review regularly for removal opportunities. What seemed essential six months ago might be dead weight now.

Sixth: make the loop visible. If you can't trace a piece of information through the full circulation, you can't debug blockages. Build observability into the loop from the start. The thirteen-commit test only works if you can actually see what's happening.

These principles aren't independent. They reinforce each other. Trusting the model means you need less corrective machinery, which means you can delete more, which means tighter coupling is feasible, which means cycle time improves. The principles form their own little loop.



Chapter Ten
The Pulse Continues

I've been talking for a while now about loops and circulation and heartbeats. Let me end somewhere quieter.

The builders of this toolkit didn't set out to make something profound. They were trying to solve practical problems -- how to help an AI system remember what worked, learn from what didn't, get better over time. The architecture emerged from those practical concerns.

But something interesting happens when you build a functional feedback loop. The system starts exhibiting properties you didn't explicitly design. It develops what you might call character -- consistent patterns of behavior that emerge from the accumulated circulation of experience.

This isn't consciousness. It isn't sentience. It's something simpler and, in its own way, more interesting: it's the shape that forms when information flows through a loop many times.

Water running through a landscape carves channels. The channels then guide where the water flows next. Given enough time, you get a river -- a stable pattern that seems designed but wasn't. It just emerged from the circulation.

The toolkit is like that. The loop has been running long enough now that patterns have carved themselves. The system responds to similar situations in similar ways, not because anyone wrote rules for those situations, but because the memory of past circulations shapes current behavior.

I find this encouraging, in a cautious way. We're building systems that genuinely learn, that genuinely improve, that carry forward the lessons of their experience. Not through mysterious processes, but through comprehensible circulation. Act, observe, store, inject, act better.

The pulse continues.

Whether this is a good thing depends entirely on what the system is learning, what it's improving toward, what lessons it's carrying forward. The loop is just a mechanism. The direction comes from elsewhere -- from the goals baked in, from the humans guiding it, from the constraints enforced along the way.

But the mechanism matters. A system that can learn is different from one that can't. A system with healthy circulation is different from one with blocked flow.

I started by saying interesting systems are like hearts, not buildings. Let me add: healthy hearts don't need constant intervention. They beat on their own, adjust their rhythm to demand, repair minor damage, maintain circulation through changing conditions.

That's what this architecture is aiming for. Not a system that needs constant tending, but one with a healthy pulse -- strong enough to sustain itself, adaptable enough to improve, constrained enough to stay useful.

The builders are still building. The loop is still circulating. New memories are being captured even now, stored, injected into future decisions.

Somewhere in that circulation, the system is getting a little better at something it wasn't good at yesterday.

That seems worth building.
