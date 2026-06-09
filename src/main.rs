mod bounty;

fn main() {
    // Call the _fetch_bounties function to fetch and filter real bounty data
    let bounties = bounty::_fetch_bounties();

    // Print the filtered bounties
    for bounty in bounties {
        println!("{:?}", bounty);
    }
}